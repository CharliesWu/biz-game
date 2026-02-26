import streamlit as st
import pandas as pd

# ==========================================
# 1. CORE BUSINESS LOGIC CLASSES
# ==========================================

class Company:
    def __init__(self, name):
        self.name = name
        self.cash = 15000000
        self.is_bankrupt = False
        self.loss_penalty_triggered = False
        self.current_loss_streak = 0 
        self.extra_pe = 0
        self.mfg_effects = []   
        self.soft_effects = []  
        self.factory_effects = [] 
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
                    comp.loss_penalty_triggered = True
            else:
                comp.current_loss_streak = 0
            
            if comp.cash < 0:
                comp.is_bankrupt = True
            
            round_results.append({'Name': name, 'Profit': net_profit, 'Cash': comp.cash, 'Total Share': comp.last_total_share, 'Status': 'Active' if not comp.is_bankrupt else 'Bankrupt'})
        return pd.DataFrame(round_results)

    def get_final_ranking(self):
        final_data = []
        for name, comp in self.companies.items():
            if comp.is_bankrupt:
                final_data.append({'Name': name, 'Final_Share': 0, 'Price': 0})
                continue
            final_pe = max(5, 10 + comp.extra_pe - (2 if comp.loss_penalty_triggered else 0))
            price = comp.last_round_profit * final_pe
            final_data.append({'Name': name, 'Final_Share': comp.last_total_share, 'Price': price})
            
        df = pd.DataFrame(final_data)
        max_share, max_price = df['Final_Share'].max(), df['Price'].max()
        df['Score'] = 0.5 * (df['Final_Share'] / (max_share if max_share > 0 else 1)) + 0.5 * (df['Price'] / (max_price if max_price > 0 else 1))
        return df.sort_values(by='Score', ascending=False)

# ==========================================
# 2. STREAMLIT UI (REWRITTEN FOR STABILITY)
# ==========================================

st.set_page_config(page_title="Automotive Sim", layout="wide")
st.title("🚗 Automotive Market Strategy Simulator")

# Initialization
if 'game' not in st.session_state:
    st.session_state.teams = ["Team 1", "Team 2", "Team 3", "Team 4"]
    st.session_state.game = Simulation(st.session_state.teams)
    st.session_state.current_round = 1
    st.session_state.history_reports = []
    st.session_state.game_over = False

# Function to handle rerun across different Streamlit versions
def safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# SIDEBAR
if not st.session_state.game_over:
    st.sidebar.header(f"Round {st.session_state.current_round} Input")
    decisions = {}
    for team in st.session_state.teams:
        st.sidebar.subheader(f"📍 {team}")
        comp = st.session_state.game.companies[team]
        dis = comp.is_bankrupt
        
        l = st.sidebar.slider(f"{team} Low-End", 0.0, 1.0, 0.5, 0.05, key=f"l_{team}_{st.session_state.current_round}", disabled=dis)
        vi = st.sidebar.selectbox(f"{team} Invest", ["None", "Manufacturing", "Software"], key=f"v_{team}_{st.session_state.current_round}", disabled=dis)
        fac = st.sidebar.checkbox(f"{team} Factory", key=f"f_{team}_{st.session_state.current_round}", disabled=dis)
        
        decisions[team] = {"low_ratio": l, "high_ratio": 1.0 - l, "vi": vi, "build_factory": fac}

    if st.sidebar.button("Submit Decisions"):
        try:
            # Execute logic
            res = st.session_state.game.execute_round(st.session_state.current_round, decisions)
            st.session_state.history_reports.append(res)
            
            if st.session_state.current_round < 4:
                st.session_state.current_round += 1
            else:
                st.session_state.game_over = True
            
            safe_rerun() # Force UI refresh
        except Exception as e:
            st.error(f"Calculation Error: {e}")

# MAIN PAGE
c1, c2 = st.columns([2, 1])
with c1:
    if st.session_state.history_reports:
        for i, rep in enumerate(reversed(st.session_state.history_reports)):
            st.write(f"### Round {len(st.session_state.history_reports) - i} Report")
            st.table(rep.style.format({"Profit": "{:,.0f}", "Cash": "{:,.0f}", "Total Share": "{:.2%}"}))
    else:
        st.info("Enter data in the sidebar and click Submit.")

with c2:
    if st.session_state.game_over:
        st.success("### Simulation Over!")
        final = st.session_state.game.get_final_ranking()
        st.write("#### Final Standings")
        st.table(final.style.format({"Final_Share": "{:.2%}", "Price": "{:,.2f}", "Score": "{:.4f}"}))
        if st.button("Restart"):
            st.session_state.clear()
            safe_rerun()
    else:
        st.write(f"### Current Round: {st.session_state.current_round}")
        st.write("Each round's decisions affect the next. Watch your cash!")
