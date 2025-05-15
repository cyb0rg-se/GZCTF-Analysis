// your_project_folder/static/script.js
document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = 'http://127.0.0.1:5001/api'; // 你的 API 地址

    const dataFetchTimeEl = document.getElementById('dataFetchTime');
    const analysisCalcTimeEl = document.getElementById('analysisCalcTime');
    const defaultParamsUsedEl = document.getElementById('defaultParamsUsed');
    const refreshDataBtn = document.getElementById('refreshDataBtn');
    
    const targetUsernameEl = document.getElementById('targetUsername');
    const minScoreEl = document.getElementById('minScore');
    const minSimilarityEl = document.getElementById('minSimilarity');
    const timeProximitySecondsEl = document.getElementById('timeProximitySeconds');
    
    const viewCachedAnalysisBtn = document.getElementById('viewCachedAnalysisBtn');
    const recalculateAnalysisBtn = document.getElementById('recalculateAnalysisBtn');
    const drawGlobalNetworkBtn = document.getElementById('drawGlobalNetworkBtn');
    const drawPersonalNetworkBtn = document.getElementById('drawPersonalNetworkBtn');
    
    const resultsAreaEl = document.getElementById('resultsArea');
    const cyDiv = document.getElementById('cy');
    let cy; 

    let currentAnalysisFullResults = null; 
    let detailedPairDataStore = []; 

    const coseLayoutOptions = {
        name: 'cose',
        idealEdgeLength: 100, nodeOverlap: 20, refresh: 20, fit: true, padding: 40,
        randomize: false, componentSpacing: 120, 
        nodeRepulsion: function( node ){ return 450000; }, 
        edgeElasticity: function( edge ){ return 120; },  
        nestingFactor: 5, gravity: 80, numIter: 1500, initialTemp: 200,
        coolingFactor: 0.95, minTemp: 1.0, animate: 'end', animationDuration: 600,
        animationEasing: 'ease-out'
    };

    const dateTimeFormatOptions = { // 通用日期时间格式化选项
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false 
    };

    function initCy(elements = []) {
        if (cy) { cy.destroy(); }
        cy = cytoscape({
            container: cyDiv, elements: elements, style: [ 
                { selector: 'node', style: { 'background-color': '#3b82f6', 'label': 'data(id)', 'color': '#ffffff', 'text-outline-color': '#3b82f6', 'text-outline-width': 2, 'font-size': '12px', 'width': 'mapData(score, 0, 2000, 25, 65)', 'height': 'mapData(score, 0, 2000, 25, 65)', 'border-width': 1.5, 'border-color': '#2563eb', 'transition-property': 'background-color, border-color', 'transition-duration': '0.2s'}},
                { selector: 'node:selected', style: { 'background-color': '#ef4444', 'border-color': '#dc2626', 'text-outline-color': '#ef4444', }},
                { selector: 'edge', style: { 'width': 'mapData(weight, 0, 1, 0.8, 4)', 'line-color': '#adb5bd', 'target-arrow-color': '#adb5bd', 'target-arrow-shape': 'triangle', 'arrow-scale': 1.2, 'curve-style': 'bezier', 'opacity': 0.6, 'transition-property': 'line-color, target-arrow-color, width, opacity', 'transition-duration': '0.2s'}},
                { selector: 'edge:selected', style: { 'line-color': '#e63946', 'target-arrow-color': '#e63946', 'width': 'mapData(weight, 0, 1, 1.5, 6)', 'opacity': 0.9 }}
            ], layout: coseLayoutOptions });
        cy.on('mouseover', 'node', function(event) { 
            const node = event.target; const { id, score, solved_count } = node.data();
            if (node.popperRef) { node.popperRef.destroy(); }
            node.popperRef = node.popper({ content: () => { let div = document.createElement('div'); div.innerHTML = `<b>${id}</b><br>分数: ${score || 'N/A'}<br>解题: ${solved_count || 'N/A'}`; div.style.backgroundColor = 'white'; div.style.padding = '5px 10px'; div.style.border = '1px solid #ccc'; div.style.borderRadius = '4px'; div.style.boxShadow = '0 2px 5px rgba(0,0,0,0.1)'; div.style.fontSize = '12px'; div.style.pointerEvents = 'none'; document.body.appendChild(div); return div; }, popper: { placement: 'top', modifiers: [ { name: 'offset', options: { offset: [0, 8] } } ] }});
        });
        cy.on('mouseout', 'node', function(event) { if (event.target.popperRef) { event.target.popperRef.destroy(); event.target.popperRef = null; }});
        cy.on('mouseover', 'edge', function(event) { 
            const edge = event.target; const metrics = edge.data('metrics_summary') || {}; const weight = edge.data('weight'); let tooltipContent = `相似度: ${weight !== undefined ? weight.toFixed(3) : 'N/A'}<br>`;
            if(metrics.j !== undefined) tooltipContent += `J: ${metrics.j} `; if(metrics.wj !== undefined) tooltipContent += `WJ: ${metrics.wj}<br>`;
            if(metrics.s !== undefined) tooltipContent += `Seq: ${metrics.s} `; if(metrics.tp_c !== undefined) tooltipContent += `TP: ${metrics.tp_c}`;
            if (edge.popperRef) { edge.popperRef.destroy(); }
            edge.popperRef = edge.popper({ content: () => { let div = document.createElement('div'); div.innerHTML = tooltipContent; div.style.backgroundColor = 'white'; div.style.padding = '5px 10px'; div.style.border = '1px solid #ccc'; div.style.borderRadius = '4px'; div.style.boxShadow = '0 2px 5px rgba(0,0,0,0.1)'; div.style.fontSize = '12px'; div.style.pointerEvents = 'none'; document.body.appendChild(div); return div; }, popper: { placement: 'top', modifiers: [ { name: 'offset', options: { offset: [0, 8] } } ] }});
        });
        cy.on('mouseout', 'edge', function(event) { if (event.target.popperRef) { event.target.popperRef.destroy(); event.target.popperRef = null; }});
    }
    initCy();

    async function fetchData(url, options = {}) { 
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: response.statusText, error: "服务器通信错误或返回了非JSON错误信息"  }));
                let errorMessage = `HTTP错误 ${response.status}: ${errorData.message || errorData.error || response.statusText}`;
                throw new Error(errorMessage);
            }
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) { return await response.json(); }
            const textResponse = await response.text();
            if (textResponse.trim() !== "") return textResponse; 
            return { message: "操作已成功发送，但服务器未返回具体JSON内容。" };
        } catch (error) { console.error(`请求 ${url} 失败:`, error); throw error; }
    }

    async function updateStatus() {
        dataFetchTimeEl.textContent = '加载中...'; 
        analysisCalcTimeEl.textContent = '加载中...';
        defaultParamsUsedEl.textContent = '预计算参数: 加载中...';
        try {
            const data = await fetchData(`${API_BASE_URL}/status`); 
            
            let fetchTimeDisplay = "N/A";
            if (data.last_data_fetch_time_iso && data.last_data_fetch_time_iso !== "N/A") {
                fetchTimeDisplay = new Date(data.last_data_fetch_time_iso).toLocaleString('zh-CN', dateTimeFormatOptions);
            }
            dataFetchTimeEl.textContent = fetchTimeDisplay;

            let analysisTimeDisplay = "无预计算结果";
            if (data.last_analysis_time_iso && data.last_analysis_time_iso !== "N/A" && 
                data.last_analysis_time_iso !== "无预计算结果" && 
                !data.last_analysis_time_iso.includes("错误") && !data.last_analysis_time_iso.includes("失败")) {
                analysisTimeDisplay = new Date(data.last_analysis_time_iso).toLocaleString('zh-CN', dateTimeFormatOptions);
            } else if (data.last_analysis_time_iso) { 
                analysisTimeDisplay = data.last_analysis_time_iso; 
            }
            analysisCalcTimeEl.textContent = analysisTimeDisplay;

            if (data.default_analysis_params_used) {
                const params = data.default_analysis_params_used;
                let paramsText = `当前预计算使用参数: 方法=${(params.methods || []).join(',')}; `;
                paramsText += `时间接近=${params.time_proximity_seconds}s; `;
                paramsText += `最低图相似度=${params.min_similarity_threshold}; `;
                paramsText += `最低用户分=${params.min_user_score}`;
                defaultParamsUsedEl.textContent = paramsText;
            } else {
                defaultParamsUsedEl.textContent = "未能获取预计算参数信息 (可能无缓存)。";
            }
        } catch (error) {
            dataFetchTimeEl.textContent = "获取状态失败"; 
            analysisCalcTimeEl.textContent = "获取状态失败";
            defaultParamsUsedEl.textContent = "获取预计算参数失败。";
            console.error("Update status failed:", error.message);
        }
    }

    if (refreshDataBtn) { 
        refreshDataBtn.addEventListener('click', async () => {
            console.log("调试日志: '刷新服务器数据' 按钮被点击。"); 
            const originalText = refreshDataBtn.textContent;
            refreshDataBtn.textContent = "刷新中 (含预计算)..."; refreshDataBtn.disabled = true;
            dataFetchTimeEl.textContent = "正在刷新原始数据..."; 
            analysisCalcTimeEl.textContent = "等待预计算...";
            resultsAreaEl.innerHTML = "<p>正在刷新服务器数据并执行后台预计算分析，请稍候...</p>";
            currentAnalysisFullResults = null; 
            initCy(); 

            try {
                const data = await fetchData(`${API_BASE_URL}/fetch_data`, { method: 'POST' });
                resultsAreaEl.innerHTML = `<p style="color:green;">${data.message || '数据刷新请求已发送，后台将进行预计算。'}</p>`;
                await updateStatus(); 
            } catch (error) {
                resultsAreaEl.innerHTML = `<p style="color:red;">刷新数据失败: ${error.message}</p>`;
                await updateStatus(); 
            }
            refreshDataBtn.textContent = originalText;
            refreshDataBtn.disabled = false;
        });
    } else {
        console.error("严重错误: 未能找到 ID 为 'refreshDataBtn' 的按钮元素。");
    }
    
    let modalFunctionsAttached = false;
    function showModal(title, contentHtml) {
        let modal = document.getElementById('detailsModal');
        let modalTitleEl = document.getElementById('detailsModalTitle'); 
        let modalBodyEl = document.getElementById('detailsModalBody'); 

        if (!modal) { 
            console.log("调试: 正在创建新的模态框 (detailsModal)");
            modal = document.createElement('div'); modal.id = 'detailsModal'; modal.className = 'modal';
            const modalContentDiv = document.createElement('div'); modalContentDiv.className = 'modal-content';
            const modalHeader = document.createElement('div'); modalHeader.className = 'modal-header';
            modalTitleEl = document.createElement('h2'); modalTitleEl.id = 'detailsModalTitle';
            const closeModalBtn = document.createElement('span'); closeModalBtn.className = 'modal-close-btn';
            closeModalBtn.innerHTML = '&times;'; closeModalBtn.setAttribute('aria-label', 'Close');
            closeModalBtn.onclick = () => { modal.style.display = 'none'; };
            modalHeader.appendChild(modalTitleEl); modalHeader.appendChild(closeModalBtn);
            modalBodyEl = document.createElement('div'); modalBodyEl.id = 'detailsModalBody';
            modalContentDiv.appendChild(modalHeader); modalContentDiv.appendChild(modalBodyEl);
            modal.appendChild(modalContentDiv); document.body.appendChild(modal);
            
            if (!modalFunctionsAttached) { //确保 window click 事件只添加一次
                 window.addEventListener('click', function(event) {
                    if (event.target == modal) { modal.style.display = "none"; }
                 });
                 modalFunctionsAttached = true;
            }
        } else {
            modalTitleEl = document.getElementById('detailsModalTitle');
            modalBodyEl = document.getElementById('detailsModalBody');
        }

        if (modalTitleEl) { modalTitleEl.textContent = title; } 
        else { console.error("错误: 未能找到模态框标题元素 (detailsModalTitle)。"); }
        if (modalBodyEl) { modalBodyEl.innerHTML = contentHtml; } 
        else { console.error("错误: 未能找到模态框内容主体元素 (detailsModalBody)。"); }
        modal.style.display = 'block';
    }

    function showPairTimelineDetails(pairIndex) {
        if (pairIndex < 0 || pairIndex >= detailedPairDataStore.length) {
            console.error("无效的选手对索引:", pairIndex); alert("无法加载该选手对的详细信息 (索引无效)。"); return;
        }
        const pairData = detailedPairDataStore[pairIndex];
        const timelineData = pairData.common_challenge_timeline_data;
        if (!timelineData) {
            console.warn("选手对数据中缺少 common_challenge_timeline_data:", pairData);
            alert("该选手对的详细时间线数据不可用。请确保后端已正确发送此数据。"); return;
        }
        if (timelineData.length === 0) {
            showModal(`${pairData.pair_names[0]} & ${pairData.pair_names[1]} - 详细信息`, "<p>这对选手没有共同解决的题目。</p>"); return;
        }
        let earliestTimeOverall = Infinity;
        timelineData.forEach(chall => { earliestTimeOverall = Math.min(earliestTimeOverall, chall.user1_time_ms, chall.user2_time_ms); });
        let detailsHtml = `<div class="timeline-details"><ul>`;
        timelineData.forEach(chall => {
            const u1Time = new Date(chall.user1_time_ms); const u2Time = new Date(chall.user2_time_ms);
            const timeDiffSeconds = Math.abs(chall.user1_time_ms - chall.user2_time_ms) / 1000;
            const u1RelTimeS = ((chall.user1_time_ms - earliestTimeOverall) / 1000).toFixed(1);
            const u2RelTimeS = ((chall.user2_time_ms - earliestTimeOverall) / 1000).toFixed(1);
            let zScoreText = "";
            if (chall.z_score_details) {
                if (chall.z_score_details.z_score !== undefined && chall.z_score_details.z_score !== "N/A") {
                    zScoreText = ` (Z-score: ${chall.z_score_details.z_score}, 均差: ${chall.z_score_details.mean_diff_seconds_all_pairs}s, 标差: ${chall.z_score_details.std_diff_seconds_all_pairs}s)`;
                } else if (chall.z_score_details.message) { zScoreText = ` (Z-score信息: ${chall.z_score_details.message})`; }
            }
            detailsHtml += `<li><strong>${chall.title || `题目ID: ${chall.id}`}</strong><div class="timeline-entry"><span class="user-solve">${chall.user1_name}:</span> ${u1Time.toLocaleTimeString('zh-CN', {hour12:false})} (相对+${u1RelTimeS}s)</div><div class="timeline-entry"><span class="user-solve">${chall.user2_name}:</span> ${u2Time.toLocaleTimeString('zh-CN', {hour12:false})} (相对+${u2RelTimeS}s)</div><div class="timeline-diff">时间差: ${timeDiffSeconds.toFixed(1)}秒 ${zScoreText}</div></li>`;
        });
        detailsHtml += `</ul></div>`;
        showModal(`${pairData.pair_names[0]} & ${pairData.pair_names[1]} - 共同解题时间线`, detailsHtml);
    }

    function getSelectedMethods() { 
        const methods = [];
        if (document.getElementById('methodJaccard').checked) methods.push('jaccard');
        if (document.getElementById('methodWeightedJaccard').checked) methods.push('weighted_jaccard');
        if (document.getElementById('methodSequence').checked) methods.push('sequence');
        if (document.getElementById('methodTimeProximity').checked) methods.push('time_proximity');
        if (document.getElementById('methodTimeDiffDist').checked) methods.push('time_diff_dist');
        return methods;
    }
    
    function renderResultsAndGraph(analysisDataContainer, sourceMessage = "分析结果") {
        if (!analysisDataContainer || !analysisDataContainer.results) {
            resultsAreaEl.innerHTML = `<p>未能获取有效的分析结果用于显示。</p>`;
            initCy(); 
            return;
        }

        const resultsData = analysisDataContainer.results;
        const calcTimeIso = analysisDataContainer.calculation_time_iso;
        const calcTimeDisplay = calcTimeIso && calcTimeIso !== "N/A" ? 
                               new Date(calcTimeIso).toLocaleString('zh-CN', dateTimeFormatOptions) : '未知或N/A';
        
        resultsAreaEl.innerHTML = `<h4>${sourceMessage} (计算于: ${calcTimeDisplay})</h4>`;
        
        const paramsUsedForThisAnalysis = analysisDataContainer.params_used;
        if (paramsUsedForThisAnalysis) {
            let paramsText = `本次分析使用参数: 方法=${(paramsUsedForThisAnalysis.methods || []).join(',')}; `;
            paramsText += `时间接近=${paramsUsedForThisAnalysis.time_proximity_seconds}s; `;
            paramsText += `图相似度=${paramsUsedForThisAnalysis.min_similarity_threshold}; `;
            paramsText += `用户分=${paramsUsedForThisAnalysis.min_user_score}`;
            if(paramsUsedForThisAnalysis.target_username) paramsText += `; 目标用户=${paramsUsedForThisAnalysis.target_username}`;
            resultsAreaEl.innerHTML += `<p style="font-size:0.85em; color:#555;">${paramsText}</p>`;
        }

        detailedPairDataStore = resultsData.similar_pairs || [];

        if (detailedPairDataStore.length > 0) {
            const currentTargetUsernameForTable = targetUsernameEl.value.trim();
            let pairsToShowInTable = detailedPairDataStore;
            if (currentTargetUsernameForTable) {
                pairsToShowInTable = detailedPairDataStore.filter(p => 
                    p.pair_names[0] === currentTargetUsernameForTable || p.pair_names[1] === currentTargetUsernameForTable
                );
            }
            
            let tableHtml = `
                <p>共找到 ${detailedPairDataStore.length} 对原始相似数据，当前筛选显示 ${pairsToShowInTable.length} 对。</p>
                <table>
                    <thead>
                        <tr>
                            <th>选手对</th><th>综合得分</th><th>Jaccard</th>
                            <th>加权Jaccard</th><th>序列相似度</th><th>时间接近(计数)</th>
                            <th>显著Z-score题数</th><th>详情</th>
                        </tr>
                    </thead>
                <tbody>`;
            
            pairsToShowInTable.slice(0, 100).forEach((pair) => {
                const originalIndex = detailedPairDataStore.findIndex(
                    p => p.pair_ids && pair.pair_ids && p.pair_ids[0] === pair.pair_ids[0] && p.pair_ids[1] === pair.pair_ids[1]
                );
                let zScoreCount = 'N/A';
                if (pair.time_distribution_analysis) { 
                    zScoreCount = pair.time_distribution_analysis.filter(r => r.z_score !== undefined && r.z_score !== "N/A" && r.z_score < -1.5).length;
                }
                tableHtml += `
                    <tr>
                        <td>${pair.pair_names[0]} & ${pair.pair_names[1]}</td>
                        <td>${pair.overall_similarity_heuristic !== undefined ? pair.overall_similarity_heuristic.toFixed(3) : 'N/A'}</td>
                        <td>${pair.jaccard !== undefined ? pair.jaccard.toFixed(3) : 'N/A'}</td>
                        <td>${pair.weighted_jaccard !== undefined ? pair.weighted_jaccard.toFixed(3) : 'N/A'}</td>
                        <td>${pair.sequence_similarity !== undefined ? pair.sequence_similarity.toFixed(3) : 'N/A'}</td>
                        <td>${pair.time_proximity ? pair.time_proximity.count : 'N/A'}</td>
                        <td>${zScoreCount}</td>
                        <td><button class="details-btn" data-pairindex="${originalIndex}">查看</button></td>
                    </tr>`;
            });
            tableHtml += '</tbody></table>'; 
            resultsAreaEl.innerHTML += tableHtml;
        } else { 
            resultsAreaEl.innerHTML += '<p>无相似选手对数据可显示。</p>'; 
        }

        // 图表通常在点击相应绘图按钮时绘制，这里先清空旧图
        initCy(); 
        if (!resultsData.network_nodes || resultsData.network_nodes.length === 0) {
            resultsAreaEl.innerHTML += '<p>无网络图节点数据。</p>';
        }
    }
    
    if (viewCachedAnalysisBtn) {
        viewCachedAnalysisBtn.addEventListener('click', async (e) => {
            const btn = e.target;
            const originalText = btn.textContent;
            btn.textContent = "加载缓存中..."; btn.disabled = true;
            resultsAreaEl.innerHTML = '<p>正在加载预计算的分析结果...</p>';
            currentAnalysisFullResults = null; initCy();

            try {
                const data = await fetchData(`${API_BASE_URL}/get_cached_analysis`);
                if (data && data.results) {
                    currentAnalysisFullResults = data; 
                    renderResultsAndGraph(currentAnalysisFullResults, "预计算分析结果");
                } else if (data && data.error) {
                    resultsAreaEl.innerHTML = `<p style="color:red;">加载缓存分析失败: ${data.error}</p>`;
                } else {
                    resultsAreaEl.innerHTML = `<p style="color:orange;">未能加载缓存的分析结果，或缓存为空。</p>`;
                }
            } catch (error) {
                resultsAreaEl.innerHTML = `<p style="color:red;">加载缓存分析时出错: ${error.message}</p>`;
            }
            btn.textContent = originalText; btn.disabled = false;
        });
    }

    if (recalculateAnalysisBtn) {
        recalculateAnalysisBtn.addEventListener('click', async (e) => {
            const btn = e.target;
            const originalButtonText = btn.textContent;
            btn.textContent = "重新计算中..."; btn.disabled = true;
            resultsAreaEl.innerHTML = '<p>正在使用当前参数重新计算分析，请稍候...</p>'; 
            currentAnalysisFullResults = null; initCy();

            const analysisParams = {
                min_user_score: parseInt(minScoreEl.value) || 0,
                min_similarity_threshold: parseFloat(minSimilarityEl.value) || 0.0,
                time_proximity_seconds: parseInt(timeProximitySecondsEl.value) || 300,
                methods: getSelectedMethods(),
                target_username: targetUsernameEl.value.trim() ? targetUsernameEl.value.trim() : null
            };
            if (analysisParams.methods.length === 0) {
                alert("请至少选择一种分析方法进行重新计算！");
                resultsAreaEl.innerHTML = '<p>请选择至少一种分析方法。</p>';
                btn.textContent = originalButtonText; btn.disabled = false; return;
            }

            try {
                const data = await fetchData(`${API_BASE_URL}/analyze`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(analysisParams)
                });
                
                if (data && data.results) { 
                    currentAnalysisFullResults = { 
                        params_used: data.analysis_parameters, // 后端 /api/analyze 应返回这个
                        calculation_time_iso: data.calculation_time_iso, // 后端 /api/analyze 应返回这个
                        results: data.results
                    };
                    renderResultsAndGraph(currentAnalysisFullResults, "按需计算的分析结果");
                } else if (data && data.error) { 
                    resultsAreaEl.innerHTML = `<p style="color:red;">重新计算分析失败: ${data.error}</p>`; 
                } else { 
                    resultsAreaEl.innerHTML = `<p style="color:red;">无法从服务器获取重新计算的分析结果。</p>`; 
                }
            } catch (error) { 
                resultsAreaEl.innerHTML = `<p style="color:red;">重新计算过程中发生错误: ${error.message}</p>`;
            }
            btn.textContent = originalButtonText; btn.disabled = false;
        });
    }
    
    function drawGraph(isPersonal) {
        if (!currentAnalysisFullResults || !currentAnalysisFullResults.results) {
            alert("请先加载或计算分析数据，再绘制图表。");
            // resultsAreaEl.innerHTML += "<p>无数据显示，无法绘制图表。</p>"; // renderResultsAndGraph 会处理
            return;
        }
        const resultsData = currentAnalysisFullResults.results;
        const graphElements = [];
        
        // --- 调试日志：检查 clientMinSimilarity 的值 ---
        const rawMinSimilarityValue = minSimilarityEl.value;
        const clientMinSimilarity = parseFloat(rawMinSimilarityValue) || 0.0;
        console.log(`绘图时使用的最小相似度阈值 (raw: "${rawMinSimilarityValue}", parsed: ${clientMinSimilarity})`);
        // --- 调试日志结束 ---

        const clientTargetUser = targetUsernameEl.value.trim();

        if (resultsData.network_nodes) {
            resultsData.network_nodes.forEach(node => {
                graphElements.push({ data: { id: node.id, score: node.score, solved_count: node.solved_count }});
            });
        }
        if (resultsData.network_edges) {
            resultsData.network_edges.forEach(edge => {
                // 确保 edge.weight 存在且是数字
                const edgeWeight = parseFloat(edge.weight);
                if (isNaN(edgeWeight)) {
                    console.warn("边的权重无效:", edge);
                    return; // 跳过此边
                }

                if (edgeWeight >= clientMinSimilarity) { 
                    if (isPersonal) {
                        if (clientTargetUser && (edge.source === clientTargetUser || edge.target === clientTargetUser)) {
                            graphElements.push({ data: { source: edge.source, target: edge.target, weight: edgeWeight, metrics_summary: edge.metrics_summary }});
                        }
                    } else {
                        graphElements.push({ data: { source: edge.source, target: edge.target, weight: edgeWeight, metrics_summary: edge.metrics_summary }});
                    }
                }
            });
        }
        
        initCy(graphElements); 
        if (cy.elements().length > 0) { 
             console.log("调试: 准备绘制图表，元素数量:", cy.elements().length);
             cy.layout(coseLayoutOptions).run();
        } else {
            // resultsAreaEl 已经由 renderResultsAndGraph 更新，这里可以补充图表部分的提示
            const graphSpecificMessage = document.createElement('p');
            graphSpecificMessage.textContent = "根据当前筛选条件，未能为关系图生成任何节点或边数据。";
            // 避免重复添加消息，如果 resultsAreaEl 已有内容
            if (!resultsAreaEl.querySelector('#graphStatusMessage')) {
                graphSpecificMessage.id = 'graphStatusMessage';
                resultsAreaEl.appendChild(graphSpecificMessage);
            } else {
                 document.getElementById('graphStatusMessage').textContent = "根据当前筛选条件，未能为关系图生成任何节点或边数据。";
            }
        }
    }

    if(drawGlobalNetworkBtn) {
        drawGlobalNetworkBtn.addEventListener('click', () => drawGraph(false));
    }
    if(drawPersonalNetworkBtn) {
        drawPersonalNetworkBtn.addEventListener('click', () => {
            if (!targetUsernameEl.value.trim()) {
                alert("绘制个人网络图需要输入目标用户名！");
                return;
            }
            drawGraph(true);
        });
    }
    
    resultsAreaEl.addEventListener('click', function(event) {
        if (event.target.classList.contains('details-btn')) {
            const pairIndex = parseInt(event.target.dataset.pairindex); 
            if (!isNaN(pairIndex) && pairIndex >= 0 && pairIndex < detailedPairDataStore.length) {
                showPairTimelineDetails(pairIndex);
            } else {
                console.error("详情按钮的 pairindex 无效或越界:", event.target.dataset.pairindex, "数据存储长度:", detailedPairDataStore.length);
                alert("无法加载此详情，数据索引无效。");
            }
        }
    });

    updateStatus();
});