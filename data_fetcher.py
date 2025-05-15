# your_project_folder/data_fetcher.py
import requests
import json
import time
import os

DATA_FILE = "scoreboard_data.json" # 缓存文件名
CACHE_DURATION_SECONDS = 300 # 缓存持续时间，例如5分钟 (300秒)
GAME_SERVER_URL = "http://your_gzctf_platform_url/api/game/${比赛ID}/scoreboard"

"""↑例如:http://127.0.0.1:8080/api/game/7/scoreboard"""

def fetch_data_from_server():
    """
    从游戏服务器获取原始数据，并保存到本地JSON文件。
    同时记录获取数据的时间戳。
    """
    try:
        headers = { # 根据你的实际请求包添加必要的头信息
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36", # 示例 User-Agent
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate", # 通常服务器会处理gzip
            "Accept-Language": "zh-CN,zh;q=0.9" # 接受的语言
            # "Host": "127.0.0.1:8880" # requests库会自动从URL中提取Host
        }
        print(f"正在从 {GAME_SERVER_URL} 获取数据...")
        response = requests.get(GAME_SERVER_URL, headers=headers, timeout=10) # 设置请求超时10秒
        response.raise_for_status() # 如果HTTP请求返回了失败的状态码 (4xx 或 5xx), 则抛出HTTPError异常
        
        data = response.json()
        data['fetch_timestamp_utc'] = time.time() # 记录获取数据时的UTC时间戳 (秒)
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2) # indent=2 使JSON文件更易读
        
        # 将UTC时间戳格式化为易读的字符串
        fetch_time_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(data['fetch_timestamp_utc']))
        print(f"数据获取成功并已保存到 {DATA_FILE}")
        return data, fetch_time_str
        
    except requests.exceptions.Timeout:
        print(f"从服务器获取数据超时: {GAME_SERVER_URL}")
        return None, "获取数据超时"
    except requests.exceptions.ConnectionError:
        print(f"无法连接到服务器: {GAME_SERVER_URL}")
        return None, "无法连接到服务器"
    except requests.exceptions.RequestException as e:
        print(f"从服务器获取数据时发生请求错误: {e}")
        return None, f"获取数据请求错误: {e}"
    except json.JSONDecodeError as e: # 捕获JSON解析错误
        print(f"解析服务器返回的JSON时出错: {e}")
        return None, "解析JSON出错"

def run_analysis(contestant_data, rarity_weights, all_challenges_info, analysis_params):
    results = {
        'similar_pairs': [],
        'network_nodes': [],
        'network_edges': []
    }
    
    user_ids = list(contestant_data.keys())
    user_name_to_id = {data['name']: uid for uid, data in contestant_data.items()}

    for uid, data in contestant_data.items():
        results['network_nodes'].append({
            'id': data['name'],
            'user_id_internal': uid,
            'score': data['total_score'],
            'solved_count': len(data['solved_set'])
        })

    user_pairs_to_compare = []
    # ... (确定 user_pairs_to_compare 的逻辑保持不变) ...
    if analysis_params.get("target_username"):
        target_name = analysis_params["target_username"]
        if target_name not in user_name_to_id:
            return {"error": f"目标用户 '{target_name}' 未在活跃选手中找到。"}
        target_uid = user_name_to_id[target_name]
        for uid_other in user_ids:
            if uid_other != target_uid:
                pair = tuple(sorted((target_uid, uid_other))) 
                user_pairs_to_compare.append(pair)
        user_pairs_to_compare = list(set(user_pairs_to_compare))
    else:
        user_pairs_to_compare = list(combinations(user_ids, 2))

    if not user_pairs_to_compare:
        return results

    for uid1, uid2 in user_pairs_to_compare:
        data1 = contestant_data[uid1]
        data2 = contestant_data[uid2]
        name1, name2 = data1['name'], data2['name']

        pair_scores_summary = {'pair_names': (name1, name2), 'pair_ids': (uid1, uid2)}
        combined_score_factors_weighted = [] 

        # ... (Jaccard, 加权Jaccard, 序列相似度等的计算逻辑保持不变) ...
        # a. Jaccard 相似度
        if "jaccard" in analysis_params["methods"]:
            j_score = calculate_jaccard_index(data1['solved_set'], data2['solved_set'])
            pair_scores_summary['jaccard'] = round(j_score, 3)
            combined_score_factors_weighted.append((j_score, 1.0))

        # b. 加权 Jaccard 相似度
        if "weighted_jaccard" in analysis_params["methods"]:
            wj_score = calculate_weighted_jaccard_index(data1['solved_set'], data2['solved_set'], rarity_weights)
            pair_scores_summary['weighted_jaccard'] = round(wj_score, 3)
            combined_score_factors_weighted.append((wj_score, 1.5))

        # c. 解题顺序相似度
        if "sequence" in analysis_params["methods"]:
            seq_score = calculate_sequence_similarity(data1['solved_sequence'], data2['solved_sequence'])
            pair_scores_summary['sequence_similarity'] = round(seq_score, 3)
            combined_score_factors_weighted.append((seq_score, 1.2))
        
        # d. 提交时间接近性分析
        time_prox_details_for_pair = {} # 用于存储时间接近性的详细结果
        if "time_proximity" in analysis_params["methods"]:
            threshold_sec = analysis_params.get("time_proximity_seconds", 300)
            close_subs_details = get_time_proximity_details(data1, data2, threshold_sec)
            time_prox_details_for_pair = { # 赋值给外层变量
                'count': len(close_subs_details),
                'threshold_seconds': threshold_sec,
                'details': close_subs_details
            }
            pair_scores_summary['time_proximity'] = time_prox_details_for_pair # 存入 pair_scores_summary
            common_solved_count = len(data1['solved_set'].intersection(data2['solved_set']))
            if common_solved_count > 0:
                 time_prox_heuristic_score = min(1.0, len(close_subs_details) / (max(1, common_solved_count / 2.0))) 
                 combined_score_factors_weighted.append((time_prox_heuristic_score, 1.8))
            elif len(close_subs_details) > 0 :
                 combined_score_factors_weighted.append((0.5, 1.8))

        # e. 提交时间差分布分析 (Z-score)
        z_score_details_for_pair = [] # 用于存储Z-score的详细结果
        if "time_diff_dist" in analysis_params["methods"]:
            significant_z_score_count = 0
            common_challenge_ids_for_dist = data1['solved_set'].intersection(data2['solved_set'])
            for chall_id_dist in common_challenge_ids_for_dist:
                dist_res_item = analyze_submission_time_diff_distribution(
                    data1, data2, contestant_data, chall_id_dist, all_challenges_info
                )
                if dist_res_item: 
                    z_score_details_for_pair.append(dist_res_item) # 赋值给外层变量
                    if 'z_score' in dist_res_item and isinstance(dist_res_item['z_score'], (int, float)):
                        if dist_res_item['z_score'] < -1.5: 
                            significant_z_score_count +=1
            pair_scores_summary['time_distribution_analysis'] = z_score_details_for_pair # 存入 pair_scores_summary
            if common_challenge_ids_for_dist:
                z_score_heuristic_score = min(1.0, significant_z_score_count / (max(1, len(common_challenge_ids_for_dist) / 2.0)))
                combined_score_factors_weighted.append((z_score_heuristic_score, 1.3))


        # --- 新增：为“详情”准备共同解题时间线数据 ---
        common_ids = data1['solved_set'].intersection(data2['solved_set'])
        common_challenge_timeline_data = []
        for chall_id in common_ids:
            # 获取此题目的 Z-score 详情 (如果已计算)
            z_score_info_for_this_chall = next((item for item in z_score_details_for_pair if item.get('challenge_id') == chall_id), None)

            common_challenge_timeline_data.append({
                'id': chall_id,
                'title': all_challenges_info.get(chall_id, {}).get('title', f'题目_{chall_id}'),
                'user1_name': name1, # 使用已获取的 name1
                'user1_time_ms': data1['solved_timed'][chall_id],
                'user2_name': name2, # 使用已获取的 name2
                'user2_time_ms': data2['solved_timed'][chall_id],
                'z_score_details': z_score_info_for_this_chall # 加入Z-score信息
            })
        # 按第一个用户的解题时间排序 (可选)
        common_challenge_timeline_data.sort(key=lambda x: x['user1_time_ms'])
        pair_scores_summary['common_challenge_timeline_data'] = common_challenge_timeline_data
        # --- 新增结束 ---

        total_weighted_score = sum(score * weight for score, weight in combined_score_factors_weighted)
        total_weights = sum(weight for _, weight in combined_score_factors_weighted)
        overall_similarity_heuristic = total_weighted_score / total_weights if total_weights > 0 else 0.0
        pair_scores_summary['overall_similarity_heuristic'] = round(overall_similarity_heuristic, 3)
        
        results['similar_pairs'].append(pair_scores_summary)
        
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
            
    results['similar_pairs'].sort(key=lambda x: x.get('overall_similarity_heuristic', 0), reverse=True)
    return results

def get_scoreboard_data(force_refresh=False):
    """
    获取计分板数据。
    优先从本地缓存文件读取，如果缓存不存在、过期或强制刷新，则从服务器获取。
    返回: (数据字典, 获取时间的字符串) 或 (None, 错误信息字符串)
    """
    if not force_refresh and os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            fetch_time_seconds = data.get('fetch_timestamp_utc', 0) # 这是Unix时间戳(秒)
            if time.time() - fetch_time_seconds < CACHE_DURATION_SECONDS:
                print(f"从缓存文件 {DATA_FILE} 加载数据。")
                fetch_time_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(fetch_time_seconds))
                return data, fetch_time_str
            else:
                print("缓存已过期，正在从服务器获取新数据。")
                return fetch_data_from_server()
        except (json.JSONDecodeError, IOError) as e:
            print(f"读取缓存文件时出错: {e}。正在从服务器获取新数据。")
            return fetch_data_from_server()
    else:
        if force_refresh:
            print("强制刷新，正在从服务器获取新数据。")
        else:
            print(f"缓存文件 {DATA_FILE} 不存在，正在从服务器获取新数据。")
        return fetch_data_from_server()

if __name__ == '__main__':
    # 用于直接测试此模块的功能
    print("测试数据获取模块...")
    # 测试强制刷新
    data, fetch_time_str = get_scoreboard_data(force_refresh=True)
    if data:
        print(f"测试获取成功，数据采集时间: {fetch_time_str}")
        print(f"总血量奖励: {data.get('bloodBonus')}")
        print(f"队伍数量: {len(data.get('items', []))}")
    else:
        print(f"测试获取失败: {fetch_time_str}")

    # 测试使用缓存 (假设上面已经成功获取并缓存了)
    # print("\n再次获取 (应使用缓存):")
    # data, fetch_time_str = get_scoreboard_data()
    # if data:
    #     print(f"数据采集时间: {fetch_time_str}")
    # else:
    #     print(f"获取失败: {fetch_time_str}")