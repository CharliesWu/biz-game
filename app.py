import streamlit as st
import pandas as pd

# --- 引入之前的 Company 和 Simulation 类 (此处简略，需包含你之前的完整类逻辑) ---
# 注意：在 Streamlit 中，我们需要把 Simulation 实例存在 st.session_state 里

st.set_page_config(page_title="商业模拟挑战赛", layout="wide")

st.title("🚗 汽车市场战略模拟器 (4轮挑战)")

# 初始化游戏状态
if 'game_started' not in st.session_state:
    st.session_state.teams = ["Team 1", "Team 2", "Team 3", "Team 4"]
    st.session_state.game = Simulation(st.session_state.teams)
    st.session_state.current_round = 1
    st.session_state.history_reports = []
    st.session_state.game_started = True
    st.session_state.game_over = False

# --- 侧边栏：输入当前轮次决策 ---
if not st.session_state.game_over:
    st.sidebar.header(f"第 {st.session_state.current_round} 轮 决策录入")
    
    current_decisions = {}
    for team in st.session_state.teams:
        st.sidebar.subheader(f"📍 {team}")
        low = st.sidebar.slider(f"{team} Low-End 投入", 0.0, 1.0, 0.5, key=f"{team}_low_{st.session_state.current_round}")
        high = 1.0 - low
        vi = st.sidebar.selectbox(f"{team} 垂直整合", ["None", "Manufacturing", "Software"], key=f"{team}_vi_{st.session_state.current_round}")
        factory = st.sidebar.checkbox(f"{team} 是否建厂", key=f"{team}_fac_{st.session_state.current_round}")
        
        current_decisions[team] = {
            "low_ratio": low,
            "high_ratio": high,
            "vi": vi,
            "build_factory": factory
        }

    if st.sidebar.button("提交本轮决策并结算"):
        # 执行逻辑
        report = st.session_state.game.execute_round(st.session_state.current_round, current_decisions)
        st.session_state.history_reports.append(report)
        
        if st.session_state.current_round < 4:
            st.session_state.current_round += 1
        else:
            st.session_state.game_over = True
        st.rerun()

# --- 主界面：显示结果 ---
col1, col2 = st.columns([2, 1])

with col1:
    if st.session_state.history_reports:
        for i, report in enumerate(st.session_state.history_reports):
            st.write(f"### 第 {i+1} 轮 市场报告")
            st.dataframe(report.style.format({"Profit": "{:,.0f}", "Cash": "{:,.0f}", "Total Share": "{:.2%}"}))
    else:
        st.info("请在左侧侧边栏输入决策并点击提交。")

with col2:
    if st.session_state.game_over:
        st.balloons()
        st.success("### 🏁 游戏结束！最终排名")
        final_ranking = st.session_state.game.get_final_ranking()
        st.dataframe(final_ranking.style.format({"Final_Share": "{:.2%}", "Price": "{:,.2f}", "Score": "{:.4f}"}))
        
        winner = final_ranking.iloc[0]['Name']
        st.header(f"🏆 冠军是: {winner}")
        
        if st.button("重启游戏"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
