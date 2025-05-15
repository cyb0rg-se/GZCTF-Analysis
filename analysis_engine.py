# your_project_folder/analysis_engine.py
from collections import defaultdict
from itertools import combinations
from difflib import SequenceMatcher
import numpy as np # 用于统计分析 (例如计算均值、标准差)
import time # 用于计时


def preprocess_data(scoreboard_data, min_user_score=0):
    """
    对从服务器获取的原始计分板数据进行预处理和筛选。
    提取选手解题信息、计算题目罕见度等。

    参数:
    - scoreboard_data (dict): 原始计分板数据。
    - min_user_score (int): 选手的最低有效总分，低于此分数的选手将被忽略。

    返回:
    - contestant_solves (dict): 处理后的选手数据字典，键为选手ID。
    - challenge_rarity_weights (dict): 题目罕见度权重字典，键为题目ID。
    - all_challenges_info (dict): 所有题目的基本信息字典，键为题目ID。
    - challenge_solve_counts (dict): 每个题目被解决的次数，键为题目ID。
    """
    contestant_solves = {} # 存储处理后的选手数据
    if not scoreboard_data or 'items' not in scoreboard_data:
        print("警告: 预处理数据为空或结构不正确。")
        return {}, {}, {}, {}

    # 1. 收集所有题目的解决次数和基本信息
    challenge_solve_counts = defaultdict(int) # 题目ID -> 解决次数
    all_challenges_info = {} # 题目ID -> {'title': ..., 'base_score': ..., 'category': ...}

    if 'challenges' in scoreboard_data and isinstance(scoreboard_data['challenges'], dict):
        for category_name, challenges_in_cat in scoreboard_data['challenges'].items():
            if isinstance(challenges_in_cat, list):
                for chall_info_raw in challenges_in_cat:
                    if isinstance(chall_info_raw, dict) and 'id' in chall_info_raw:
                        chall_id = chall_info_raw['id']
                        all_challenges_info[chall_id] = {
                            'title': chall_info_raw.get('title', f"题目_{chall_id}"),
                            'base_score': chall_info_raw.get('score', 0), # 题目的基础分值
                            'category': chall_info_raw.get('category', '未知分类')
                        }
                        # 'solved' 字段通常表示有多少队伍/人解出了这道题
                        challenge_solve_counts[chall_id] = chall_info_raw.get('solved', 0)
                    else:
                        print(f"警告: 在分类 '{category_name}' 中发现格式不正确的题目信息: {chall_info_raw}")
            else:
                 print(f"警告: 分类 '{category_name}' 的题目列表格式不正确: {challenges_in_cat}")

    else:
        print("警告: 原始数据中缺少 'challenges' 键或其格式不正确，将尝试从选手提交中推断题目信息。")


    # 2. 处理每个选手的数据
    active_user_count = 0
    for user_data_raw in scoreboard_data.get('items', []):
        if not isinstance(user_data_raw, dict):
            print(f"警告: 发现格式不正确的用户条目: {user_data_raw}")
            continue

        user_id = user_data_raw.get('id')
        user_name = user_data_raw.get('name', f"用户_{user_id}")
        total_score = user_data_raw.get('score', 0)

        if user_id is None: # 跳过没有ID的用户
            print(f"警告: 用户 {user_name} 缺少ID，已跳过。")
            continue
        if total_score < min_user_score: # 跳过分数过低的选手
            continue

        solved_challenges_list_for_user = []
        if isinstance(user_data_raw.get('solvedChallenges'), list):
            for chall_solve_info in user_data_raw['solvedChallenges']:
                if not isinstance(chall_solve_info, dict):
                    print(f"警告: 用户 {user_name} (ID: {user_id}) 的解题记录格式不正确: {chall_solve_info}")
                    continue

                challenge_id = chall_solve_info.get('id')
                solve_time = chall_solve_info.get('time') # 这是毫秒级时间戳

                # 确保题目ID有效且时间有效 (大于0，因为数据中有-62135596800000这样的无效时间)
                if challenge_id is not None and solve_time is not None and solve_time > 0:
                    # 如果题目信息中没有这个题，动态添加（尽管这表示数据可能不一致）
                    if challenge_id not in all_challenges_info:
                        all_challenges_info[challenge_id] = {
                            'title': f"题目_{challenge_id} (动态添加)",
                            'base_score': chall_solve_info.get('score', 0), # 使用解题得分作为基础分
                            'category': '动态添加'
                        }
                        print(f"警告: 题目ID {challenge_id} 未在全局题目列表中找到，已动态添加。")

                    # 如果 challenge_solve_counts 没有被 'challenges' 部分填充，则可以从这里统计
                    # (但优先使用 'challenges' 部分的 'solved' 字段，因为它更权威)
                    # challenge_solve_counts[challenge_id] += 1

                    solved_challenges_list_for_user.append({
                        'id': challenge_id, # 题目ID
                        'time': solve_time, # 解决时间 (毫秒)
                        'score_obtained': chall_solve_info.get('score', all_challenges_info[challenge_id]['base_score']) # 本次解题获得的实际分数
                    })
                else:
                    print(f"警告: 用户 {user_name} 的题目 {challenge_id} 解题时间无效或ID缺失: {solve_time}")

        if not solved_challenges_list_for_user: # 跳过没有有效解题记录的选手
            continue

        # 按解题时间升序排序
        solved_challenges_list_for_user.sort(key=lambda x: x['time'])

        contestant_solves[user_id] = {
            'name': user_name,
            'total_score': total_score,
            'solved_set': {s['id'] for s in solved_challenges_list_for_user}, # 解出的题目ID集合
            'solved_sequence': [s['id'] for s in solved_challenges_list_for_user], # 按时间顺序的解题ID列表
            'solved_timed': {s['id']: s['time'] for s in solved_challenges_list_for_user}, # 题目ID -> 解题时间(毫秒)映射
            'solved_full_info': solved_challenges_list_for_user # 保留完整的解题信息列表
        }
        active_user_count += 1

    print(f"预处理完成，筛选后得到 {active_user_count} 名活跃选手。")

    # 3. 计算题目罕见度权重
    challenge_rarity_weights = {} # 题目ID -> 罕见度权重
    # 如果 challenge_solve_counts 为空 (例如 'challenges' 部分缺失或无效), 重新统计
    if not challenge_solve_counts and active_user_count > 0:
        print("全局题目解决数统计为空，尝试从选手提交中重新统计...")
        for uid, data in contestant_solves.items():
            for chall_id in data['solved_set']:
                challenge_solve_counts[chall_id] += 1

    if challenge_solve_counts:
        # max_solves = max(challenge_solve_counts.values()) if challenge_solve_counts else 1
        # 使用总活跃选手数量作为罕见度计算的一个基准，避免max_solves太小导致权重差异不明显
        total_active_solvers = active_user_count if active_user_count > 0 else 1

        for chall_id in all_challenges_info.keys(): # 遍历所有已知的题目ID
            count = challenge_solve_counts.get(chall_id, 0) # 获取解决次数，默认为0
            if count > 0:
                # 解决人数越少，权重越高。可以尝试不同的公式。
                # 例如：1.0 / count，或者 (total_active_solvers / count)
                challenge_rarity_weights[chall_id] = total_active_solvers / count
            else:
                # 没人解决的题目，给予一个较高的权重 (例如，相当于只有0.5个人解决)
                challenge_rarity_weights[chall_id] = total_active_solvers / 0.5
    else:
        print("警告: 无法计算题目罕见度权重，因为题目解决数统计为空。")

    return contestant_solves, challenge_rarity_weights, all_challenges_info, challenge_solve_counts


# --- 相似度计算函数 ---
def calculate_jaccard_index(set1, set2):
    """计算两个集合的Jaccard Index (杰卡德相似系数)"""
    if not isinstance(set1, set) or not isinstance(set2, set):
        return 0.0 #确保输入是集合
    if not set1 and not set2: return 1.0 # 如果两个集合都为空，定义为完全相似
    if not set1 or not set2: return 0.0 # 如果其中一个为空而另一个不为空，则不相似

    intersection_len = len(set1.intersection(set2))
    union_len = len(set1.union(set2))

    return intersection_len / union_len if union_len != 0 else 0.0

def calculate_weighted_jaccard_index(set1, set2, weights):
    """计算加权的Jaccard Index。weights是一个字典，key为元素，value为权重。"""
    if not isinstance(set1, set) or not isinstance(set2, set):
        return 0.0
    if not weights: return calculate_jaccard_index(set1, set2) # 如果没有权重，退化为普通Jaccard

    if not set1 and not set2: return 1.0
    if not set1 or not set2: return 0.0

    intersect_set = set1.intersection(set2)
    union_set = set1.union(set2)

    # 对于权重字典中可能不存在的题目ID，给予一个默认的低权重 (例如0.1)，避免忽略这些题目
    default_weight = 0.1

    intersect_weight = sum(weights.get(item, default_weight) for item in intersect_set)
    union_weight = sum(weights.get(item, default_weight) for item in union_set)

    return intersect_weight / union_weight if union_weight != 0 else 0.0

def calculate_sequence_similarity(seq1, seq2):
    """使用 difflib.SequenceMatcher 计算两个序列的相似度比率。"""
    if not seq1 and not seq2: return 1.0
    if not seq1 or not seq2: return 0.0
    # isjunk=None 表示没有需要特殊处理的“垃圾”元素
    matcher = SequenceMatcher(None, seq1, seq2)
    return matcher.ratio() # 返回一个[0,1]的浮点数，表示相似度

def get_time_proximity_details(user1_data, user2_data, time_threshold_seconds):
    """
    获取两位选手共同解决的题目中，提交时间在指定阈值内的题目详情。
    时间阈值单位为秒。
    """
    common_ids = user1_data['solved_set'].intersection(user2_data['solved_set'])
    close_submissions = [] # 存储时间接近的提交详情

    if not common_ids:
        return close_submissions

    for chall_id in common_ids:
        time1_ms = user1_data['solved_timed'].get(chall_id)
        time2_ms = user2_data['solved_timed'].get(chall_id)

        if time1_ms is not None and time2_ms is not None:
            diff_ms = abs(time1_ms - time2_ms) # 毫秒级差值
            diff_seconds = diff_ms / 1000.0 # 转换为秒

            if diff_seconds <= time_threshold_seconds:
                close_submissions.append({
                    'challenge_id': chall_id,
                    # 'challenge_title': all_challenges_info.get(chall_id, {}).get('title', f"题目_{chall_id}"), # 可选：添加题目名称
                    'user1_time_ms': time1_ms,
                    'user2_time_ms': time2_ms,
                    'diff_seconds': round(diff_seconds, 2) # 保留两位小数
                })
    return close_submissions

# 修改 analyze_submission_time_diff_distribution 函数，使其接收预计算的统计数据
def analyze_submission_time_diff_distribution(user1_data, user2_data, challenge_id, challenge_stats):
    """
    分析特定选手对 (user1, user2) 在特定题目 (challenge_id) 上的提交时间差，
    与该题目的预计算时间差分布统计量 (均值、标准差) 进行比较。
    返回一个包含Z-score等信息的字典。

    参数:
    - user1_data, user2_data: 选手数据字典。
    - challenge_id: 题目ID。
    - challenge_stats: 包含该题目预计算统计量 {'mean': ..., 'std': ...} 的字典。

    返回:
    - 包含Z-score等统计信息的字典，或包含错误/信息消息的字典。
    """
    # 确保两位选手都解决了此题 (尽管调用前通常会检查)
    if challenge_id not in user1_data['solved_timed'] or \
       challenge_id not in user2_data['solved_timed']:
        # 理论上不应该发生，因为这个函数是在共同解题上调用的
        return {'challenge_id': challenge_id, 'message': "选手未共同解决此题或时间数据无效。"}

    # 检查预计算的统计数据是否可用且有效
    if not challenge_stats or 'mean' not in challenge_stats or 'std' not in challenge_stats:
         return {'challenge_id': challenge_id, 'message': "该题目预计算统计量不可用。"}


    mean_diff_seconds = challenge_stats['mean']
    std_diff_seconds = challenge_stats['std']

    # 计算当前分析的这对选手 (user1, user2) 在此题上的提交时间差
    pair_time1_ms = user1_data['solved_timed'][challenge_id]
    pair_time2_ms = user2_data['solved_timed'][challenge_id]
    pair_actual_diff_seconds = abs(pair_time1_ms - pair_time2_ms) / 1000.0

    z_score = None
    if std_diff_seconds < 1e-9: # 使用一个很小的阈值判断标准差是否接近零
        # 如果标准差接近零，并且这对选手的时间差与均值也接近，则Z-score为0
        # 否则，时间差显著偏离均值，这种情况下的Z-score可以视为无限大或无限小，这里返回None表示计算无效
        if abs(pair_actual_diff_seconds - mean_diff_seconds) < 1e-9:
             z_score = 0.0
        else:
             z_score = None # 无法计算有意义的Z-score
             #print(f"警告: 题目ID {challenge_id} 的时间差标准差接近零，但这对选手的时间差不接近均值。Z-score设定为None。") # 调试日志

    else:
        z_score = (pair_actual_diff_seconds - mean_diff_seconds) / std_diff_seconds

    # Z-score 越小（特别是负值），说明这对选手的提交时间差远小于平均水平，可能更“可疑”
    return {
        'challenge_id': challenge_id,
        # 'title': all_challenges_info.get(challenge_id, {}).get('title', f"题目_{challenge_id}"), # 题目名称将在调用处添加
        'pair_diff_seconds': round(pair_actual_diff_seconds, 2),
        'mean_diff_seconds_all_pairs': round(mean_diff_seconds, 2),
        'std_diff_seconds_all_pairs': round(std_diff_seconds, 2),
        'z_score': round(z_score, 3) if z_score is not None else "N/A"
    }


def run_analysis(contestant_data, rarity_weights, all_challenges_info, analysis_params):
    """
    主分析函数，根据指定的参数对选手数据进行多维度相似性分析。

    参数:
    - contestant_data (dict): 预处理后的选手数据。
    - rarity_weights (dict): 题目罕见度权重。
    - all_challenges_info (dict): 所有题目的信息。
    - analysis_params (dict): 分析参数，包含:
        - "methods": list, 需要执行的分析方法列表。
        - "time_proximity_seconds": int, 时间接近性判断的阈值 (秒)。
        - "min_similarity_threshold": float, 用于筛选关系图边的最小综合相似度。
        - "target_username": str or None, 如果指定，则只分析与该用户相关的选手对。

    返回:
    - results (dict): 包含分析结果的字典，如相似选手对列表、网络图节点和边等。
    """
    start_time = time.time() # 开始计时
    print("分析引擎启动...") # 添加启动日志

    results = {
        'similar_pairs': [],    # 存储详细的选手对相似度信息
        'network_nodes': [],    # 用于关系图的节点数据
        'network_edges': []     # 用于关系图的边数据
    }

    if not contestant_data: # 如果没有有效的选手数据，提前返回
        print("警告 (run_analysis): 传入的 contestant_data 为空。无法进行分析。")
        return results

    user_ids = list(contestant_data.keys())
    user_name_to_id = {data['name']: uid for uid, data in contestant_data.items() if 'name' in data}

    # 1. 准备关系图的节点数据
    print("正在准备网络图节点数据...")
    for uid, data in contestant_data.items():
        results['network_nodes'].append({
            'id': data.get('name', f"User_{uid}"), # Cytoscape 使用 id 作为唯一标识
            'user_id_internal': uid, # 保留内部ID
            'score': data.get('total_score', 0),
            'solved_count': len(data.get('solved_set', set()))
        })
    print(f"已准备 {len(results['network_nodes'])} 个节点。")


    # --- 优化步骤：预计算每个题目在所有解决者之间的时间差统计量 (用于Z-score) ---
    challenge_time_stats = {} # 存储每个题目的 { 'mean': ..., 'std': ... }
    if "time_diff_dist" in analysis_params.get("methods", []):
        print("正在预计算每个题目在所有解决者之间的时间差统计量 (用于Z-score)...")
        all_challenge_ids = all_challenges_info.keys()
        processed_challenge_count = 0
        for chall_id in all_challenge_ids:
            processed_challenge_count += 1
            # if processed_challenge_count % 50 == 0 or processed_challenge_count == len(all_challenge_ids):
            #     print(f"  已处理 {processed_challenge_count}/{len(all_challenge_ids)} 个题目统计量...") # 可选进度

            # 收集所有解决了此题的选手ID
            user_ids_solved_this_chall = [
                uid for uid, data in contestant_data.items()
                if chall_id in data.get('solved_timed', {}) # 使用 .get() 防止 solved_timed 键不存在
            ]

            # 只有解决人数 >= 3 且有时间数据才计算统计量
            if len(user_ids_solved_this_chall) >= 3:
                all_time_diffs_for_chall_seconds = []
                # 计算所有解出此题的选手对之间的提交时间差 (秒)
                for pair_combo_ids in combinations(user_ids_solved_this_chall, 2):
                    uid_a, uid_b = pair_combo_ids
                    # 再次使用 .get() 确保时间数据存在
                    time_a_ms = contestant_data[uid_a]['solved_timed'].get(chall_id)
                    time_b_ms = contestant_data[uid_b]['solved_timed'].get(chall_id)
                    if time_a_ms is not None and time_b_ms is not None:
                         all_time_diffs_for_chall_seconds.append(abs(time_a_ms - time_b_ms) / 1000.0)

                # 确保有足够的时间差数据点来计算标准差
                if len(all_time_diffs_for_chall_seconds) >= 2: # 至少需要2个差值数据点 (即至少3人解出)
                     mean_diff_seconds = np.mean(all_time_diffs_for_chall_seconds)
                     std_diff_seconds = np.std(all_time_diffs_for_chall_seconds)
                     # 只有标准差不接近零时才存储统计量，避免后续Z-score计算问题
                     if std_diff_seconds >= 1e-9:
                        challenge_time_stats[chall_id] = {
                            'mean': mean_diff_seconds,
                            'std': std_diff_seconds
                        }
        print("题目时间差统计量预计算完成。")
    # --- 优化步骤结束 ---


    # 2. 确定要比较的选手对
    user_pairs_to_compare = []
    if analysis_params.get("target_username"): # 如果指定了目标用户
        target_name = analysis_params["target_username"]
        if target_name not in user_name_to_id:
            print(f"警告 (run_analysis): 目标用户 '{target_name}' 未在活跃选手中找到。")
            results['error'] = f"目标用户 '{target_name}' 未在活跃选手中找到。"
            return results

        target_uid = user_name_to_id[target_name]
        for uid_other in user_ids:
            # 确保不与自己比较，并且只比较目标用户与其他人 (避免重复，sorted tuple handled below)
            if uid_other != target_uid:
                 user_pairs_to_compare.append(tuple(sorted((target_uid, uid_other)))) # 确保对的顺序一致

        user_pairs_to_compare = list(set(user_pairs_to_compare)) # 去重
    else: # 否则，比较所有可能的选手对
        user_pairs_to_compare = list(combinations(user_ids, 2))

    if not user_pairs_to_compare:
        print("没有可供比较的选手对。")
        return results

    # --- 添加日志输出：开始计算 ---
    total_pairs_to_compare = len(user_pairs_to_compare)
    print(f"开始计算 {total_pairs_to_compare} 对选手相似度...")
    # ------------------------------

    # 3. 遍历选手对进行分析
    pairs_processed_count = 0 # 用于进度计数
    for uid1, uid2 in user_pairs_to_compare:
        pairs_processed_count += 1
        # --- 添加可选日志输出：显示计算进度 (例如，每处理 10% 或一定数量) ---
        # 只有在计算对数较多时才输出进度，避免刷屏
        if total_pairs_to_compare > 100 and (pairs_processed_count % (total_pairs_to_compare // 10) == 0 or pairs_processed_count == total_pairs_to_compare):
             print(f"  已处理 {pairs_processed_count}/{total_pairs_to_compare} 对...")
        # ----------------------------------------------------------------------


        data1 = contestant_data.get(uid1) # 使用 .get() 避免 KeyError
        data2 = contestant_data.get(uid2)

        if not data1 or not data2: # 如果某个用户数据缺失，跳过这对
            print(f"警告 (run_analysis): 用户数据缺失，跳过对 {uid1}-{uid2}") # 这行代码已经存在
            continue

        name1, name2 = data1.get('name', f"User_{uid1}"), data2.get('name', f"User_{uid2}")

        pair_scores_summary = {'pair_names': (name1, name2), 'pair_ids': (uid1, uid2)}
        combined_score_factors_weighted = []
        common_challenge_ids_for_pair = data1.get('solved_set', set()).intersection(data2.get('solved_set', set())) # 提取共同解题一次

        # a. Jaccard 相似度
        if "jaccard" in analysis_params.get("methods", []):
            # 直接使用共同解题集合和各自的解题集合
            set1 = data1.get('solved_set', set())
            set2 = data2.get('solved_set', set())
            # 重新计算 Jaccard，虽然 common_ids_for_pair 已知交集，但为了代码清晰
            j_score = calculate_jaccard_index(set1, set2)
            pair_scores_summary['jaccard'] = round(j_score, 3)
            combined_score_factors_weighted.append((j_score, 1.0))

        # b. 加权 Jaccard 相似度
        if "weighted_jaccard" in analysis_params.get("methods", []):
             set1 = data1.get('solved_set', set())
             set2 = data2.get('solved_set', set())
             wj_score = calculate_weighted_jaccard_index(set1, set2, rarity_weights)
             pair_scores_summary['weighted_jaccard'] = round(wj_score, 3)
             combined_score_factors_weighted.append((wj_score, 1.5))

        # c. 解题顺序相似度
        if "sequence" in analysis_params.get("methods", []):
            seq1 = data1.get('solved_sequence', [])
            seq2 = data2.get('solved_sequence', [])
            seq_score = calculate_sequence_similarity(seq1, seq2)
            pair_scores_summary['sequence_similarity'] = round(seq_score, 3)
            combined_score_factors_weighted.append((seq_score, 1.2))

        # d. 提交时间接近性分析
        if "time_proximity" in analysis_params.get("methods", []):
            threshold_sec = analysis_params.get("time_proximity_seconds", 300)
            close_subs_details = get_time_proximity_details(data1, data2, threshold_sec)
            pair_scores_summary['time_proximity'] = {
                'count': len(close_subs_details),
                'threshold_seconds': threshold_sec,
                'details': close_subs_details
            }
            # 启发式评分: 接近提交数 / (共同解题数 / 2) (至少1)
            if common_challenge_ids_for_pair: # 使用前面提取的共同题目列表
                 time_prox_heuristic_score = min(1.0, len(close_subs_details) / (max(1, len(common_challenge_ids_for_pair) / 2.0)))
                 combined_score_factors_weighted.append((time_prox_heuristic_score, 1.8))
            elif len(close_subs_details) > 0 :
                 # 如果没有共同解题（不应该发生，因为close_subs_details基于共同题目），
                 # 但时间接近详情里有东西，可能数据有误或逻辑问题，给一个基础分
                 combined_score_factors_weighted.append((0.5, 1.8))


        # e. 提交时间差分布分析 (Z-score)
        dist_analysis_results_for_pair = []
        if "time_diff_dist" in analysis_params.get("methods", []):
            significant_z_score_count = 0 # 计算显著负 Z-score 的题目数量

            # 遍历共同解题，使用预计算的统计量
            for chall_id_z in common_challenge_ids_for_pair:
                # 获取预计算的统计量
                stats_for_this_challenge = challenge_time_stats.get(chall_id_z)

                # 只对有有效预计算统计量的题目进行 Z-score 计算
                if stats_for_this_challenge:
                    dist_res_item = analyze_submission_time_diff_distribution(
                        data1, data2, chall_id_z, stats_for_this_challenge
                    )
                    if dist_res_item: # analyze_submission_time_diff_distribution 返回None或字典
                        # 添加题目名称到结果中
                        dist_res_item['title'] = all_challenges_info.get(chall_id_z, {}).get('title', f"题目_{chall_id_z}")
                        dist_analysis_results_for_pair.append(dist_res_item)
                        # 判断Z-score是否显著小于平均水平
                        if 'z_score' in dist_res_item and isinstance(dist_res_item['z_score'], (int, float)):
                            if dist_res_item['z_score'] < -1.5: # 使用 -1.5 作为显著阈值
                                significant_z_score_count +=1
                # else:
                    # print(f"调试: 题目 {chall_id_z} 无有效统计量，跳过Z-score计算。") # 可选调试日志


            pair_scores_summary['time_distribution_analysis'] = dist_analysis_results_for_pair

            # 启发式评分：显著负 Z-score 题数 / (共同解题数 / 2) (至少1)
            if common_challenge_ids_for_pair: # 使用前面提取的共同题目列表
                 z_score_heuristic_score = min(1.0, significant_z_score_count / (max(1, len(common_challenge_ids_for_pair) / 2.0)))
                 combined_score_factors_weighted.append((z_score_heuristic_score, 1.3)) # 给予一个权重


        # --- 为“详情”准备共同解题时间线数据 ---
        # 遍历共同解题，组织时间线数据
        current_pair_timeline_data = []
        # 从已经计算好的 Z-score 结果中获取信息 (即 pair_scores_summary['time_distribution_analysis'])
        z_score_analysis_from_summary = pair_scores_summary.get('time_distribution_analysis', [])

        for chall_id_tl in common_challenge_ids_for_pair: # 使用前面提取的共同题目列表
            # 查找当前题目的Z-score信息
            z_score_info_for_this_chall = next(
                (item for item in z_score_analysis_from_summary if item.get('challenge_id') == chall_id_tl),
                None
            )

            # 确保获取到有效的解题时间，尽管preprocess_data应该已经筛选了
            time1_ms_tl = data1.get('solved_timed', {}).get(chall_id_tl)
            time2_ms_tl = data2.get('solved_timed', {}).get(chall_id_tl)

            if time1_ms_tl is not None and time2_ms_tl is not None:
                 current_pair_timeline_data.append({
                    'id': chall_id_tl,
                    'title': all_challenges_info.get(chall_id_tl, {}).get('title', f'题目_{chall_id_tl}'),
                    'user1_name': name1,
                    'user1_time_ms': time1_ms_tl,
                    'user2_name': name2,
                    'user2_time_ms': time2_ms_tl,
                    'z_score_details': z_score_info_for_this_chall # 加入Z-score信息
                 })

        # 按user1的解题时间排序
        current_pair_timeline_data.sort(key=lambda x: x.get('user1_time_ms', float('inf'))) # 使用get并提供默认值处理可能的None

        pair_scores_summary['common_challenge_timeline_data'] = current_pair_timeline_data
        # --- 共同解题时间线数据准备结束 ---


        # 计算综合得分 - 这里使用了硬编码的权重，可以根据需要调整
        total_weighted_score = sum(score * weight for score, weight in combined_score_factors_weighted)
        total_weights = sum(weight for _, weight in combined_score_factors_weighted)
        overall_similarity_heuristic = total_weighted_score / total_weights if total_weights > 0 else 0.0
        pair_scores_summary['overall_similarity_heuristic'] = round(overall_similarity_heuristic, 3)

        results['similar_pairs'].append(pair_scores_summary)

        # 添加到关系图的边数据中 - 根据整体相似度阈值筛选
        if overall_similarity_heuristic >= analysis_params.get("min_similarity_threshold", 0.0):
             results['network_edges'].append({
                'source': name1,
                'target': name2,
                'weight': round(overall_similarity_heuristic, 3),
                'metrics_summary': {
                    'j': pair_scores_summary.get('jaccard', 'N/A'),
                    'wj': pair_scores_summary.get('weighted_jaccard', 'N/A'),
                    's': pair_scores_summary.get('sequence_similarity', 'N/A'),
                    'tp_c': pair_scores_summary.get('time_proximity', {}).get('count', 'N/A')
                }
            })

    # --- 添加日志输出：计算完成 ---
    print("选手相似度计算完成，正在排序和组织结果...")
    # ------------------------------

    results['similar_pairs'].sort(key=lambda x: x.get('overall_similarity_heuristic', 0), reverse=True)

    end_time = time.time() # 结束计时
    duration = end_time - start_time
    print(f"分析引擎运行完成。总耗时: {duration:.2f} 秒。")
    # ------------------------------


    return results


if __name__ == '__main__':
    # 用于直接测试此模块的功能
    print("测试分析引擎模块...")

    # 假设 scoreboard_data.json 存在且包含有效数据
    # 您可能需要先运行 data_fetcher.py 或通过 app.py 获取一次数据
    import json
    import os
    # 尝试从 data_fetcher 导入 DATA_FILE，如果 data_fetcher 不在同一目录，需要调整导入路径
    try:
        from data_fetcher import DATA_FILE
    except ImportError:
        # 如果导入失败，假设数据文件在当前目录
        DATA_FILE = "scoreboard_data.json"
        print(f"警告: 无法从 data_fetcher 导入 DATA_FILE，假设数据文件为 {DATA_FILE}。")


    if not os.path.exists(DATA_FILE):
        print(f"错误: 找不到原始数据文件 {DATA_FILE}。请先运行 data_fetcher.py 或通过 app.py 获取数据。")
    else:
        try:
            print(f"正在加载原始数据文件: {DATA_FILE}")
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                raw_scoreboard_data = json.load(f)
            print("原始数据加载成功。")

            # 定义测试参数
            test_analysis_params = {
                "methods": ["jaccard", "weighted_jaccard", "sequence", "time_proximity", "time_diff_dist"],
                "time_proximity_seconds": 300,
                "min_similarity_threshold": 0.3, # 示例阈值
                "min_user_score": 100, # 示例最低分数
                "target_username": None # 或指定一个用户名进行测试，例如 "某个用户名"
            }
            print(f"\n测试分析参数: {test_analysis_params}")

            # 预处理数据
            print("正在预处理数据...")
            contestant_data, rarity_weights, all_challenges_info, _ = preprocess_data(raw_scoreboard_data, min_user_score=test_analysis_params["min_user_score"])
            print("数据预处理完成。")


            if contestant_data:
                # 运行分析
                analysis_results = run_analysis(
                    contestant_data,
                    rarity_weights,
                    all_challenges_info,
                    test_analysis_params
                )

                print("\n分析结果摘要:")
                print(f"找到 {len(analysis_results.get('similar_pairs', []))} 对相似选手。")
                print(f"生成 {len(analysis_results.get('network_nodes', []))} 个网络节点。")
                print(f"生成 {len(analysis_results.get('network_edges', []))} 条网络边 (高于阈值 {test_analysis_params['min_similarity_threshold']})。")

                # 打印前几对相似度最高的选手
                print("\n部分相似度结果 (前5对):")
                for i, pair in enumerate(analysis_results.get('similar_pairs', [])[:5]):
                    pair_names = pair.get('pair_names', ('N/A', 'N/A'))
                    overall_score = pair.get('overall_similarity_heuristic', 'N/A')
                    print(f"  {i+1}. {pair_names[0]} & {pair_names[1]}: 综合得分={overall_score}")
                    # print(f"     详情: {pair}") # 打印完整详情用于调试

            else:
                 print("预处理后没有可分析的选手数据。请检查最低分数设置或原始数据。")

        except Exception as e:
            print(f"测试分析引擎时发生未预期的错误: {e}")
            import traceback
            traceback.print_exc() # 打印完整的错误栈