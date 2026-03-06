import streamlit as st
import pandas as pd
import streamlit.components.v1 as components

# ==========================================
# 1. CORE BUSINESS LOGIC
# ==========================================
class Company:
    def __init__(self, name):
        self.name = name
        self.cash = 7000000 
        self.is_bankrupt = False
        self.ever_had_consecutive_loss = False
        self.last_round_profit = 0 
        self.extra_pe = 0
        self.mfg_effects, self.soft_effects, self.factory_effects = [], [], []
        # Starting share for 8 teams is 12.5% (1/8)
        self.prev_low_share = 0.125
        self.prev_high_share = 0.125

    def get_unit_profit(self, current_round):
        low_p, high_p = 500, 1000
        for start, end, l_b, h_b in self.mfg_effects:
            if start <= current_round <= end: low_p += l_b; high_p += h_b
        for start, l_b, h_b in self.soft_effects:
            if current_round >= start: low_p += l_b; high_p += h_b
        return low_p, high_p

    def get_multiplier_data(self, current_round):
        mult = 1.0
        for start in self.factory_effects:
            if current_round >= start: mult *= 1.05
        return mult

    def get_display_pe(self): return max(5, 10 + self.extra_pe)

class SimulationEngine:
    def __init__(self):
        self.teams = [f"Team {i}" for i in range(1, 9)]
        self.companies = {name: Company(name) for name in self.teams}
        self.current_round, self.history, self.decision_history = 1, [], []
        self.round_decisions, self.submitted_teams = {}, set()
        self.game_over, self.alpha = False, 0.6 

    def run_market_logic(self):
        active_teams = [t for t in self.teams if not self.companies[t].is_bankrupt]
        if len(self.submitted_teams) < len(active_teams): return False
        
        # Market Scaled to 200,000 (80k*2 / 20k*2)
        low_market, high_market = 160000, 40000
        round_results = []
        default_share = 1.0 / len(active_teams) if active_teams else 0.125

        for name in self.teams:
            comp = self.companies[name]
            d = self.round_decisions.get(name, {'low_ratio': 0.125, 'vi': 'None', 'build_factory': False})
            self.decision_history.append({'Round': self.current_round, 'Team': name, 'Low %': f"{d.get('low_ratio',0):.0%}", 'VI': d['vi'], 'Factory': "Yes" if d['build_factory'] else "No"})
            
            if comp.is_bankrupt:
                round_results.append({'Team': name, 'Op Profit': 0, 'Net Profit': 0, 'Cash Balance': comp.cash, 'Total Share': 0, 'Market Cap': 0})
                continue

            m = comp.get_multiplier_data(self.current_round)
            w_l, w_h = d['low_ratio'] * m, (1 - d['low_ratio']) * m
            
            # Simplified global normalization logic for brevity
            s_l = sum((self.round_decisions.get(t, {'low_ratio': 0}).get('low_ratio', 0) * self.companies[t].get_multiplier_data(self.current_round)) for t in active_teams)
            s_h = sum(((1-self.round_decisions.get(t, {'low_ratio': 0}).get('low_ratio', 0)) * self.companies[t].get_multiplier_data(self.current_round)) for t in active_teams)

            new_l = w_l/s_l if s_l > 0 else default_share
            new_h = w_h/s_h if s_h > 0 else default_share
            act_l = (self.alpha * comp.prev_low_share) + ((1 - self.alpha) * new_l)
            act_h = (self.alpha * comp.prev_high_share) + ((1 - self.alpha) * new_h)
            comp.prev_low_share, comp.prev_high_share = act_l, act_h
            
            u_l, u_h = comp.get_unit_profit(self.current_round)
            op_profit = (act_l * low_market * u_l) + (act_h * high_market * u_h)
            inv_cost = (3e6 if "Mfg" in d['vi'] else 0) + (1.5e6 if "Soft" in d['vi'] else 0) + (5e6 if d['build_factory'] else 0)
            
            if "Soft" in d['vi']: comp.extra_pe += 1; comp.soft_effects.append((self.current_round + 1, 5, 10))
            if "Mfg" in d['vi']: comp.mfg_effects.append((self.current_round + 1, self.current_round + 2, 50, 100))
            if d['build_factory']: comp.factory_effects.append(self.current_round + 1)

            net_profit = op_profit - inv_cost
            comp.cash += net_profit
            market_cap = max(0.0, op_profit * comp.get_display_pe())
            if comp.cash < 0: comp.is_bankrupt = True
            
            round_results.append({'Team': name, 'Op Profit': op_profit, 'Net Profit': net_profit, 'Cash Balance': comp.cash, 'Total Share': (act_l*low_market + act_h*high_market)/200000, 'Market Cap': market_cap, 'PE': comp.get_display_pe()})

        df = pd.DataFrame(round_results)
        df['Mkt Cap Rank'] = df['Market Cap'].rank(ascending=False, method='min').astype(int)
        self.history.append(df); self.submitted_teams, self.round_decisions = set(), {}
        if self.current_round >= 4: self.game_over = True
        else: self.current_round += 1
        return True

# ==========================================
# 2. UI LOGIC
# ==========================================
@st.cache_resource
def get_game(): return SimulationEngine()
game = get_game()

st.set_page_config(page_title="Strategic Simulation", layout="wide")
st.title("🚗 8-Team Strategic Simulation Dashboard")

# Color Rank logic: Medalists (1-3), Green (4-6), Red (7-8)
def style_results(df):
    def color_map(val):
        if val == 1: return 'background-color: #FFD700; color: black'
        if val == 2: return 'background-color: #C0C0C0; color: black'
        if val == 3: return 'background-color: #CD7F32; color: white'
        if 4 <= val <= 6: return 'background-color: #C8E6C9; color: #1B5E20'
        return 'background-color: #FFCDD2; color: #B71C1C'
    return df.style.format({"Total Share": "{:.2%}", "Cash Balance": "${:,.0f}", "Market Cap": "${:,.0f}"}).map(color_map, subset=['Mkt Cap Rank'])

role = st.sidebar.selectbox("Role", ["Observer"] + game.teams)
if st.sidebar.button("RESET"): st.cache_resource.clear(); st.rerun()

# 2-Row Grid for Status
st.subheader("Submission Status")
r1, r2 = st.columns(4), st.columns(4)
for i, t in enumerate(game.teams):
    status = "✅" if t in game.submitted_teams else "⏳"
    if game.companies[t].is_bankrupt: status = "💀"
    (r1[i] if i < 4 else r2[i-4]).metric(t, status)

if game.history:
    st.write(f"### Round {len(game.history)} Results")
    st.dataframe(style_results(game.history[-1]), hide_index=True, use_container_width=True)

if role.startswith("Team") and not game.game_over and not game.companies[role].is_bankrupt:
    with st.form("input"):
        l_in = st.slider("Decision 1: Low-end Capacity %", 0, 100, 50, 5) / 100.0
        vi = st.selectbox("Decision 2: VI Investment", ["None", "Mfg ($3M)", "Soft ($1.5M)"])
        fac = st.checkbox("Decision 3: Build Factory ($5M)")
        if st.form_submit_button("Submit"):
            game.round_decisions[role] = {'low_ratio': l_in, 'vi': vi, 'build_factory': fac}
            game.submitted_teams.add(role); st.rerun()

if role == "Observer" and not game.game_over and len(game.submitted_teams) > 0:
    if st.button("🚀 PROCESS ROUND"): game.run_market_logic(); st.balloons(); st.rerun()

if game.game_over:
    st.header("🏆 Final Standings")
    st.dataframe(game.history[-1].sort_values("Mkt Cap Rank"), hide_index=True)
