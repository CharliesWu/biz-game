import streamlit as st
import pandas as pd

# ==========================================
# 1. 核心业务逻辑类 (必须包含在 app.py 中)
# ==========================================

class Company:
    def __init__(self, name):
        self.name = name
        self.cash = 15000000
        self.is_bankrupt = False
        self.loss_count = 0  # 是否发生过连续亏损
        self.current_loss_streak = 0 
        
        self.extra_pe = 0
        self.mfg_effects = []   # (start, end, low_bonus, high_bonus)
        self.soft_effects = []  # (start, low_bonus, high_bonus)
        self.factory_effects = [] # (start_round)
        
        self.last_round_profit = 0
        self.last_total_share = 0

    def get_unit_profit(self, current_round):
        low_p, high_p = 500, 1000
        for start, end, l_b, h_b in self.mfg_effects:
            if start <= current_round <= end:
                low_p += l_b
                high_p += h_b
        for start, l_b, h_b in self.soft_effects:
            if current_round >= start:
                low_p += l_b
                high_p += h_b
        return low_p, high_p

    def get_multiplier(self, current_round):
        mult = 1.0
        for start in self.factory_effects:
            if current_round >= start:
                mult *= 1.1
        return mult

class Simulation:
    def __init__(self, names):
        self.companies = {name: Company(name) for name in names}

    def execute_round(self, round_num, all_decisions):
        low_market, high_market = 80000, 20000
        round_results = []
        
        # 计算加权投入
        weighted_low = {}
        weighted_high = {}
        for name, comp in self.companies.items():
            if comp.is_bankrupt:
                weighted_low[name], weighted_high[name] = 0, 0
                continue
            
            dec = all_decisions[name]
            m = comp.get_multiplier(round_num)
            weighted_low[name] = dec['low_ratio'] * m
            weighted_high[name] = dec['high_ratio'] * m

        sum_low = sum(weighted_low.values())
        sum_high = sum(weighted_high.values())
        
        for name, comp in self.companies.items():
            if comp.is_bankrupt:
                round_results.append({'Name': name, 'Profit': 0, 'Cash': comp.cash, 'Total Share': 0, 'Status': 'Bankrupt'})
                continue

            low_share = weighted_low[name] / sum_low if sum_low > 0 else 1/len(self.companies)
            high_share = weighted_high[name] / sum_high if sum_high > 0 else 1/len(self.companies)
            
            sales_low = low_share * low_market
            sales_high = high_share * high_market
            
            u_low, u_high = comp.get_unit_profit(round_num)
            gross_profit = (sales_low * u_low) + (sales_high * u_high)
            
            dec = all_decisions[name]
            inv_cost = 0
            if dec['vi'] == 'Manufacturing':
                inv_cost += 3000000
                comp.mfg_effects.append((round_num + 1, round_num + 2, 100, 200))
            elif dec['vi'] == 'Software':
                inv_cost += 1500000
                comp.soft_effects.append((round_num + 1, 5, 10))
                comp.extra_pe += 1
            
            if dec['build_factory']:
                inv_cost += 5000000
                comp.factory_effects.append(round_num + 2)
            
            net_profit = gross_profit - inv_cost
            comp.cash += net_profit
            comp.last_round_profit = net_profit
            comp.last_total_share = (sales_low + sales_high) / 100000
            
            if net_profit < 0:
                comp.current_loss_streak += 1
                if comp.current_loss_streak >= 2:
                    comp.loss_count = 1
            else:
                comp.current_loss_streak = 0
            
            if comp.cash < 0:
                comp.is_bankrupt = True
            
            round_results.append({
                'Name': name, 'Profit': net_profit, 'Cash': comp.cash, 
                'Total Share': comp.last_total_share, 'Status': 'Active' if not comp.is_bankrupt else 'Bankrupt'
            })
        return pd.DataFrame(round_results)

    def get_final_ranking(self):
        final_data = []
        for name, comp in self.companies.items():
            if comp.is_bankrupt:
                final_data.append({'Name': name, 'Final_Share': 0, 'Price': 0})
                continue
            
            final_pe = 10 + comp.extra_pe
            if comp.loss_count > 0:
                final_pe -= 2
            final_pe = max(5, final_pe)
            
            price = comp.last_round_profit * final_pe
            final_data.append({'Name': name, 'Final_Share': comp.last_total_share, 'Price': price})
            
        df = pd.DataFrame(final_data)
        max_share = df['Final_Share'].max()
        max_price = df['Price'].max()
        
        # 避免除以0
        df['Score'] = 0.5 * (df['Final_Share'] / (max_share if max_share > 0 else 1)) + \
                      0.5 * (df['Price'] / (max_price if max_price > 0 else 1))
        return df.sort_values(by='Score', ascending=False)

# ==========================================
# 2. Streamlit UI 界面部分
# ==========================================

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

# --- 侧边栏：决策录入 ---
if not st.session_state.game_over:
    st.sidebar.header(f"第 {st.session_state.current_round} 轮 决策录入")
    
    current_decisions = {}
    for team in st.session_state.teams:
        st.sidebar.subheader(f"📍 {team}")
        # 如果公司破产，禁用输入
        is_disabled = st.session_state.game.companies[team].is_bankrupt
        
        low = st.sidebar.slider(f"{team} Low-End 比例", 0.0, 1.0, 0.5, 0.05, 
                               key=f"{team}_low_{st.session_state.current_round}",
                               disabled=is_disabled)
        high = 1.0 - low
        vi = st.sidebar.selectbox(f"{team} 垂直整合", ["None", "Manufacturing", "Software"], 
                                 key=f"{team}_vi_{st.session_state.current_round}",
                                 disabled=is_disabled)
        factory = st.sidebar.checkbox(f"{team} 是否建厂", 
                                     key=f"{team}_fac_{st.session_state.current_round}",
                                     disabled=is_disabled)
        
        current_decisions[team] = {
            "low_ratio": low,
            "high_ratio": high,
            "vi": vi,
            "build_factory": factory
        }

    if st.sidebar.button("结算本轮数据"):
        report = st.session_state.game.execute_round(st.session_state.current_round, current_decisions)
        st.session_state.history_reports.append(report)
        
        if st.session_state.current_round < 4:
            st.session_state.current_round += 1
        else:
            st.session_state.game_over = True
        st.rerun()

# --- 主界面：结果显示 ---
col1, col2 = st.columns([2, 1])

with col1:
    if st.session_state.history_reports:
        # 倒序显示，最新的在最上面
        for i, report in enumerate(reversed(st.session_state.history_reports)):
            r_num = len(st.session_state.history_reports) - i
            st.write(f"### 第 {r_num} 轮 市场报告")
            st.dataframe(report.style.format({
                "Profit": "{:,.0f}", 
                "Cash": "{:,.0f}", 
                "Total Share": "{:.2%}"
            }), use_container_width=True)
    else:
        st.info("💡 游戏说明：在左侧设置各队的投入比例和投资计划，然后点击『结算本轮数据』。")

with col2:
    if st.session_state.game_over:
        st.balloons()
        st.success("### 🏁 游戏结束！")
        final_ranking = st.session_state.game.get_final_ranking()
        st.write("#### 最终排行榜")
        st.dataframe(final_ranking.style.format({
            "Final_Share": "{:.2%}", 
            "Price": "{:,.2f}", 
            "Score": "{:.4f}"
        }), use_container_width=True)
        
        winner = final_ranking.iloc[0]['Name']
        st.header(f"🏆 冠军: {winner}")
        
        if st.button("重新开始游戏"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    else:
        st.write(f"### 进度: 第 {st.session_state.current_round} / 4 轮")
        st.metric("市场总需求", "100,000 单位")
