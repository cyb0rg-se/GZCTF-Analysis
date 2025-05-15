# your_project_folder/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import data_fetcher # 你的数据获取模块
import analysis_engine # 你的分析引擎模块
import time
import os
import json
from datetime import datetime, timezone # 确保导入

app = Flask(__name__)
CORS(app)

SCOREBOARD_DATA_FILE = data_fetcher.DATA_FILE # 从 data_fetcher 获取文件名
ANALYSIS_RESULTS_FILE = "analysis_results.json" # 缓存分析结果的文件名

# 定义一套用于预计算的默认参数
DEFAULT_ANALYSIS_PARAMS = {
    "methods": ["jaccard", "weighted_jaccard", "sequence", "time_proximity", "time_diff_dist"],
    "time_proximity_seconds": 300,
    "min_similarity_threshold": 0.0, # 预计算时包含所有可能的边，前端再按需过滤
    "min_user_score": 0, # 预计算时筛选用户，这个参数会传给 preprocess_data
    "target_username": None 
}

def _perform_and_cache_default_analysis():
    """
    读取最新的 scoreboard 数据，执行默认参数的分析，并缓存结果。
    """
    app.logger.info("后台开始执行默认分析并缓存...")
    # 1. 获取当前最新的scoreboard数据 (不强制刷新，使用缓存或data_fetcher的逻辑)
    raw_data, _ = data_fetcher.get_scoreboard_data(force_refresh=False) 
    if not raw_data:
        app.logger.error("错误: 无法加载 scoreboard 数据进行默认分析。")
        return False

    try:
        # 2. 数据预处理
        # min_user_score 在 DEFAULT_ANALYSIS_PARAMS 中定义，用于此次预处理
        min_score_for_preprocessing = DEFAULT_ANALYSIS_PARAMS.get("min_user_score", 0)
        
        contestant_data, rarity_weights, all_challenges_info, _ = \
            analysis_engine.preprocess_data(raw_data, min_user_score=min_score_for_preprocessing) 
            
        analysis_output = {}
        if not contestant_data:
            app.logger.warn("警告: 预处理后无选手数据，无法执行默认分析。")
            analysis_output = {
                'params_used': DEFAULT_ANALYSIS_PARAMS,
                'calculation_time_unix': time.time(),
                'calculation_time_iso': datetime.now(timezone.utc).isoformat(), # 使用 timezone.utc
                'results': {'similar_pairs': [], 'network_nodes': [], 'network_edges': [], 'message': '预处理后无活跃选手数据'}
            }
        else:
            # 3. 执行分析 (移除 min_user_score 因为已在预处理中应用)
            run_params_for_engine = {k: v for k, v in DEFAULT_ANALYSIS_PARAMS.items() if k != "min_user_score"}

            analysis_results_obj = analysis_engine.run_analysis(
                contestant_data,
                rarity_weights,
                all_challenges_info,
                run_params_for_engine 
            )
            analysis_output = {
                'params_used': DEFAULT_ANALYSIS_PARAMS, # 保存的是完整的默认参数记录
                'calculation_time_unix': time.time(),
                'calculation_time_iso': datetime.now(timezone.utc).isoformat(), # 使用 timezone.utc
                'results': analysis_results_obj
            }
        
        # 4. 保存结果到文件
        with open(ANALYSIS_RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(analysis_output, f, ensure_ascii=False, indent=2)
        app.logger.info(f"默认分析结果已保存到 {ANALYSIS_RESULTS_FILE}")
        return True
    except Exception as e:
        app.logger.error(f"执行并缓存默认分析时出错: {e}", exc_info=True)
        return False

@app.route('/api/fetch_data', methods=['POST'])
def force_fetch_data():
    # 这个接口现在只负责获取最新的 scoreboard_data.json
    # 预计算分析将在获取成功后异步触发或由独立机制调用
    data, fetch_time_str_from_fetcher = data_fetcher.get_scoreboard_data(force_refresh=True)
    
    response_message = ""
    fetch_time_for_response = ""

    if data:
        # 原始数据获取成功，现在触发后台预计算
        app.logger.info("原始数据获取成功，准备触发后台默认分析...")
        
        # 为了不阻塞此请求，实际生产中可以将 _perform_and_cache_default_analysis() 放入后台任务队列
        # 这里为了简单，我们同步调用，但前端可能需要等待或得到一个“正在后台处理”的消息
        analysis_cached_ok = _perform_and_cache_default_analysis() # 同步执行
        
        response_message = '原始数据获取成功。' + \
                           ("后台默认分析已完成并缓存。" if analysis_cached_ok else "后台默认分析执行失败，请检查服务器日志。")
        
        # fetch_time_str_from_fetcher 是格式化好的，或者我们从data中重新获取时间戳并格式化
        raw_fetch_ts = data.get('fetch_timestamp_utc', 0)
        if raw_fetch_ts > 0:
            fetch_time_for_response = datetime.fromtimestamp(raw_fetch_ts, timezone.utc).isoformat()
        else:
            fetch_time_for_response = "N/A (时间戳无效)"
            
        return jsonify({
            'message': response_message,
            'fetch_time_iso': fetch_time_for_response # 返回原始数据的获取时间 (ISO格式)
        })
    else:
        # fetch_time_str_from_fetcher 在失败时可能包含错误信息
        return jsonify({'message': f'原始数据获取失败: {fetch_time_str_from_fetcher}', 'fetch_time_iso': None}), 500


@app.route('/api/status', methods=['GET'])
def get_status():
    scoreboard_fetch_time_iso = "N/A"
    scoreboard_source_info = "原始数据状态未知"
    
    if os.path.exists(SCOREBOARD_DATA_FILE): # 使用从 data_fetcher 导入的常量
        try:
            with open(SCOREBOARD_DATA_FILE, 'r', encoding='utf-8') as f:
                s_data = json.load(f)
            s_fetch_ts = s_data.get('fetch_timestamp_utc', 0)
            if s_fetch_ts > 0:
                s_utc_dt = datetime.fromtimestamp(s_fetch_ts, timezone.utc)
                scoreboard_fetch_time_iso = s_utc_dt.isoformat()
                scoreboard_source_info = '已缓存的原始数据'
            else:
                scoreboard_source_info = '缓存的原始数据时间戳无效'
        except Exception as e:
            app.logger.error(f"读取原始数据缓存 ({SCOREBOARD_DATA_FILE}) 出错: {e}")
            scoreboard_source_info = '读取原始数据缓存错误'

    analysis_calc_time_iso = "N/A"
    analysis_params_used = None
    analysis_source_info = "无预计算的分析结果"

    if os.path.exists(ANALYSIS_RESULTS_FILE):
        try:
            with open(ANALYSIS_RESULTS_FILE, 'r', encoding='utf-8') as f:
                analysis_cache = json.load(f)
            analysis_calc_time_iso = analysis_cache.get('calculation_time_iso', "N/A")
            analysis_params_used = analysis_cache.get('params_used')
            analysis_source_info = '已缓存的预计算分析结果'
        except Exception as e:
            app.logger.error(f"读取分析结果缓存 ({ANALYSIS_RESULTS_FILE}) 出错: {e}")
            analysis_source_info = '读取分析结果缓存错误'
            
    return jsonify({
        'last_data_fetch_time_iso': scoreboard_fetch_time_iso, # 原始计分板数据的获取时间
        'scoreboard_source_info': scoreboard_source_info,
        'last_analysis_time_iso': analysis_calc_time_iso,   # 预计算分析结果的生成时间
        'default_analysis_params_used': analysis_params_used, # 预计算时使用的参数
        'analysis_source_info': analysis_source_info
    })

@app.route('/api/get_cached_analysis', methods=['GET'])
def get_cached_analysis():
    if os.path.exists(ANALYSIS_RESULTS_FILE):
        try:
            with open(ANALYSIS_RESULTS_FILE, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
            # 返回的是包含 'params_used', 'calculation_time_iso', 'results' 的整个对象
            return jsonify(analysis_data) 
        except Exception as e:
            app.logger.error(f"读取或发送分析缓存文件 ({ANALYSIS_RESULTS_FILE}) 失败: {e}", exc_info=True)
            return jsonify({"error": "读取分析缓存失败", "details": str(e)}), 500
    else:
        return jsonify({"error": "尚无缓存的分析结果，请先刷新服务器数据以生成。", 
                        "results": None, 
                        "params_used": None, 
                        "calculation_time_iso": None}), 404

@app.route('/api/analyze', methods=['POST']) # 这个接口现在用于“按需重新计算”
def analyze_data_on_demand():
    frontend_params = request.json
    if not frontend_params:
        return jsonify({"error": "请求体必须是 JSON 格式"}), 400

    app.logger.info(f"收到按需分析请求，参数: {frontend_params}")

    raw_data, _ = data_fetcher.get_scoreboard_data(force_refresh=False) # 使用当前缓存的scoreboard数据
    if not raw_data:
        raw_data_fetch_time_iso = "N/A"
        try: # 尝试从已失效的raw_data中获取时间戳
            raw_data_fetch_time_iso = datetime.fromtimestamp(raw_data.get('fetch_timestamp_utc',0), timezone.utc).isoformat() if raw_data.get('fetch_timestamp_utc',0) > 0 else "N/A"
        except: pass
        return jsonify({"error": f"加载计分板数据失败，无法进行按需分析。", "data_fetch_time_iso": raw_data_fetch_time_iso }), 500
    
    raw_data_fetch_time_iso = datetime.fromtimestamp(raw_data['fetch_timestamp_utc'], timezone.utc).isoformat()


    min_user_score_from_frontend = frontend_params.get("min_user_score", 0)
    
    try:
        contestant_data, rarity_weights, all_challenges_info, _ = \
            analysis_engine.preprocess_data(raw_data, min_user_score=min_user_score_from_frontend)
        if not contestant_data:
             return jsonify({
                 "message": "按需分析：根据您的筛选，未找到活跃选手。", 
                 "data_fetch_time_iso": raw_data_fetch_time_iso,
                 "analysis_parameters": frontend_params, # 返回的是用于本次计算的前端参数
                 "results": {'similar_pairs': [], 'network_nodes': [], 'network_edges': [], 'message': '按需分析：预处理后无活跃选手数据'}
            })
        
        # 从 frontend_params 中提取 run_analysis 需要的参数
        run_params_for_engine = {
            "methods": frontend_params.get("methods", DEFAULT_ANALYSIS_PARAMS["methods"]), # 如果前端没传，用默认的
            "time_proximity_seconds": frontend_params.get("time_proximity_seconds", DEFAULT_ANALYSIS_PARAMS["time_proximity_seconds"]),
            "min_similarity_threshold": frontend_params.get("min_similarity_threshold", DEFAULT_ANALYSIS_PARAMS["min_similarity_threshold"]),
            "target_username": frontend_params.get("target_username", None)
            # min_user_score 已经在 preprocess_data 中使用，不传入 run_analysis
        }

        on_demand_results_obj = analysis_engine.run_analysis(
            contestant_data,
            rarity_weights,
            all_challenges_info,
            run_params_for_engine 
        )
        return jsonify({
            "message": "按需分析完成",
            "data_fetch_time_iso": raw_data_fetch_time_iso, # 使用的 scoreboard 的采集时间
            "analysis_parameters": frontend_params,     # 本次分析使用的参数
            "calculation_time_iso": datetime.now(timezone.utc).isoformat(), # 本次按需计算的时间
            "results": on_demand_results_obj
        })
    except Exception as e:
        app.logger.error(f"按需分析过程中出错: {e}", exc_info=True)
        return jsonify({"error": f"按需分析过程中出错: {str(e)}"}), 500

# --- 原有的静态文件服务路由 ---
@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

@app.route('/<path:filename>')
def serve_static_files_from_root_for_html_references(filename):
    return app.send_static_file(filename)

if __name__ == '__main__':
    if not app.debug:
        import logging
        logging.basicConfig(level=logging.INFO)
    app.logger.info("Flask 应用准备启动...")
    
    # # 首次启动时，如果分析结果文件不存在，并且原始数据文件存在，则尝试触发一次默认分析
    # if not os.path.exists(ANALYSIS_RESULTS_FILE):
    #     app.logger.info(f"{ANALYSIS_RESULTS_FILE} 不存在，检查是否需要启动时预计算。")
    #     if os.path.exists(SCOREBOARD_DATA_FILE):
    #         app.logger.info(f"发现 {SCOREBOARD_DATA_FILE}，将在启动时执行一次默认分析。")
    #         _perform_and_cache_default_analysis()
    #     else:
    #         app.logger.warn(f"原始计分板数据 ({SCOREBOARD_DATA_FILE}) 也不存在，无法在启动时执行默认分析。请先刷新一次服务器数据。")
            
    app.run(debug=True, host='0.0.0.0', port=5001)