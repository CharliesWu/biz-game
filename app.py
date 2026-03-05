import streamlit as st
import pandas as pd

# ==========================================
# 1. CORE BUSINESS LOGIC
# ==========================================
class Company:
    def __init__(self, name):
        self.name = name
        self.cash = 7000000 
        self.is_bankrupt = False
        self.ever_had_consecutive_loss = False
        self.last_round_profit = 0 # 统一变量名，修复报错
        self.extra_pe = 0
        self.mfg_effects = []   
        self.soft_effects = []  
        self.factory_effects = [] 
        
        self.prev_low_share = 0.25
        self.prev_high_share = 0.25

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

    def get_multiplier_data(self, current_round):
        mult, active_from_past = 1.0, False
        for start in self.factory_effects:
            if current_round >= start:
                mult *= 1.05
                active_from_past = True
        return mult, active_from_past

    def get_display_pe(self):
        return max(5, 10 + self.extra_pe)

class SimulationEngine:
    def __init__(self):
        self.teams = ["Team 1", "Team 2", "Team 3", "Team 4"]
        self.companies = {name: Company(name) for name in self.teams}
        self.current_round = 1
        self.history = []
        self.decision_history = [] 
        self.round_decisions = {} 
        self.submitted_teams = set()
        self.game_over = False
        self.alpha = 0.6 

    def submit_team_decision(self, team_name, dec):
        self.round_decisions[team_name] = dec
        self.submitted_teams.add(team_name)

    def run_market_logic(self):
        if len(self.submitted_teams) < 4: return False
        
        low_market, high_market = 80000, 20000
        round_results = []
        active_count = sum(1 for c in self.companies.values() if not c.is_bankrupt)
        default_share = 1.0 / active_count if active_count > 0 else 0.25

        for name, d in self.round_decisions.items():
            self.decision_history.append({
                'Round': self.current_round, 'Team': name,
                'Low %': f"{d['low_ratio']:.0%}", 'High %': f"{d['high_ratio']:.0%}",
                'VI': d['vi'], 'Building This Round': "Yes" if d['build_factory'] else "No"
            })
        
        w_low, w_high = {}, {}
        for name in self.teams:
            comp = self.companies[name]
            if comp.is_bankrupt:
                w_low[name], w_high[name] = 0.0, 0.0
            else:
                d = self.round_decisions[name]
                m, _ = comp.get_multiplier_data(self.current_round)
                w_low[name] = float(d['low_ratio'] * m)
                w_high[name] = float(d['high_ratio'] * m)

        s_low_total, s_high_total = sum(w_low.values()), sum(w_high.values())

        for name in self.teams:
            comp = self.companies[name]
            if comp.is_bankrupt:
                round_results.append({
                    'Team': name, 'Op Profit': 0.0, 'Net Profit': 0.0, 'Cash Balance': comp.cash, 
                    'Total Share': 0.0, 'Low Share': 0.0, 'High Share': 0.0, 
                    'PE': 0.0, 'Building This Round': 'Bankrupt', 'Market Cap': 0.0
                })
                continue

            new_l = w_low[name]/s_low_total if s_low_total > 0 else default_share
            new_h = w_high[name]/s_high_total if s_high_total > 0 else default_share
            act_l = (self.alpha * comp.prev_low_share) + ((1 - self.alpha) * new_l)
            act_h = (self.alpha * comp.prev_high_share) + ((1 - self.alpha) * new_h)
            comp.prev_low_share, comp.prev_high_share = act_l, act_h
            
            u_l, u_h = comp.get_unit_profit(self.current_round)
            op_profit = (act_l * low_market * u_l) + (act_h * high_market * u_h)
            
            d = self.round_decisions[name]
            inv_cost = (3000000 if d['vi']=='Manufacturing' else 0) + \
                       (1500000 if d['vi']=='Software' else 0) + \
                       (5000000 if d['build_factory'] else 0)
            
            if d['vi'] == 'Software': 
                comp.extra_pe += 1
                comp.soft_effects.append((self.current_round + 1, 5, 10))
            if d['vi'] == 'Manufacturing': 
                comp.mfg_effects.append((self.current_round + 1, self.current_round + 2, 50, 100))
            if d['build_factory']: 
                comp.factory_effects.append(self.current_round + 1)

            net_profit = op_profit - inv_cost
            
            # 检查连续亏损
            if comp.last_round_profit < 0 and net_profit < 0: 
                comp.ever_had_consecutive_loss = True
            
            comp.cash += net_profit
            comp.last_round_profit = net_profit # 统一更新

            market_cap = max(0.0, op_profit * comp.get_display_pe())
            if comp.cash < 0: comp.is_bankrupt = True
            
            round_results.append({
                'Team': name, 'Op Profit': op_profit, 'Net Profit': net_profit, 
                'Cash Balance': comp.cash, 'Total Share': (act_l * low_market + act_h * high_market) / 100000, 
                'Low Share': act_l, 'High Share': act_h, 
                'PE': comp.get_display_pe(), 'Building This Round': "Yes" if d['build_factory'] else "No", 
                'Market Cap': market_cap
            })

        df = pd.DataFrame(round_results)
        df['Share Rank'] = df['Total Share'].rank(ascending=False, method='min').astype(int)
        df['Mkt Cap Rank'] = df['Market Cap'].rank(ascending=False, method='min').astype(int)
        
        self.history.append(df)
        self.submitted_teams, self.round_decisions = set(), {}
        if self.current_round >= 4: self.game_over = True
        else: self.current_round += 1
        return True

    def get_final_scores(self):
        final_list = []
        for name in self.teams:
            c = self.companies[name]
            pe = max(5, 10 + c.extra_pe - (2 if c.ever_had_consecutive_loss else 0))
            # 修复：使用正确的变量名 last_round_profit
            price = 0 if c.is_bankrupt else c.last_round_profit * pe
            final_list.append({'Team': name, 'Final_Share': c.prev_low_share * 0.8 + c.prev_high_share * 0.2, 'Price': price})
        
        # 实际从历史数据抓取更准确的最终份额
        for i, entry in enumerate(final_list):
            name = entry['Team']
            if not self.companies[name].is_bankrupt:
                entry['Final_Share'] = self.history[-1][self.history[-1]['Team'] == name]['Total Share'].values[0]

        df = pd.DataFrame(final_list)
        ms, mp = df['Final_Share'].max(), df['Price'].max()
        df['Score'] = 0.5*(df['Final_Share']/(ms if ms>0 else 1)) + 0.5*(df['Price']/(mp if mp>0 else 1))
        return df.sort_values('Score', ascending=False)

# ==========================================
# 2. UI LOGIC & STYLING
# ==========================================
@st.cache_resource
def get_shared_game(): return SimulationEngine()
game = get_shared_game()

st.set_page_config(page_title="Strategic Simulation", layout="wide")
st.title("🚗 Automotive Strategic Simulation Dashboard")

def style_results(df):
    def color_ranks(val):
        if val == 1: return 'background-color: #FFD700; color: black; font-weight: bold' # Gold
        if val == 2: return 'background-color: #C0C0C0; color: black; font-weight: bold' # Silver
        if val == 3: return 'background-color: #CD7F32; color: white; font-weight: bold' # Bronze
        if val == 4: return 'background-color: #E1F5FE; color: #01579B; font-weight: bold' # Ice Blue for 4th
        return 'font-weight: bold'

    cols = ['Team', 'Low Share', 'High Share', 'Total Share', 'Share Rank', 
            'Op Profit', 'Net Profit', 'Cash Balance', 'PE', 
            'Building This Round', 'Market Cap', 'Mkt Cap Rank']

    return df[cols].style.format({
        "Low Share": "{:.2%}", "High Share": "{:.2%}", "Total Share": "{:.2%}", 
        "Op Profit": "${:,.0f}", "Net Profit": "${:,.0f}", "Cash Balance": "${:,.0f}", 
        "PE": "{:.1f}", "Market Cap": "${:,.0f}"
    }).map(color_ranks, subset=['Share Rank', 'Mkt Cap Rank'])\
      .set_properties(subset=['Total Share', 'PE'], **{'font-weight': 'bold'})

# Sidebar
st.sidebar.title("Sim Control")
role = st.sidebar.selectbox("Select Role", ["--- Select ---", "Teacher/Observer", "Team 1", "Team 2", "Team 3", "Team 4"])

st.sidebar.markdown("---")
if role == "Teacher/Observer":
    st.sidebar.subheader("🚨 Danger Zone")
    confirm_reset = st.sidebar.checkbox("Double check to enable reset")
    if st.sidebar.button("RESET ALL GAME DATA", disabled=not confirm_reset):
        st.cache_resource.clear()
        st.rerun()

if st.sidebar.button("🔄 Sync Screen"): st.rerun()

if role == "--- Select ---":
    st.info("Please select your role in the sidebar.")
    st.stop()

# Progress Status
st.subheader(f"Round {game.current_round} Progress")
s_cols = st.columns(4)
for i, t in enumerate(game.teams):
    status = "✅ Ready" if t in game.submitted_teams else "⏳ Thinking"
    if game.companies[t].is_bankrupt: status = "💀 Bankrupt"
    s_cols[i].metric(t, status)

# Dashboard
if game.history:
    st.divider()
    latest = game.history[-1]
    st.write(f"## 📊 Round {len(game.history)} Official Results")
    st.table(style_results(latest))

# Form for Team Input
if role.startswith("Team") and not game.game_over:
    if role in game.submitted_teams:
        st.success(f"Strategy for {role} locked.")
    elif game.companies[role].is_bankrupt:
        st.error("Bankrupt.")
    else:
        with st.form("decision_form"):
            st.write(f"### Strategy Input: {role} (R{game.current_round})")
            l_alloc = st.slider("Low-End allocation %", 0.0, 1.0, 0.5, 0.05)
            vi_choice = st.selectbox("Vertical Integration", ["None", "Manufacturing", "Software"])
            build_f = st.checkbox("Build New Factory ($5M)")
            if st.form_submit_button("Submit Strategy"):
                game.submit_team_decision(role, {"low_ratio": l_alloc, "high_ratio": 1.0-l_alloc, "vi": vi_choice, "build_factory": build_f})
                st.rerun()

# Processing Logic
if len(game.submitted_teams) == 4 and not game.game_over and role == "Teacher/Observer":
    if st.button("🚀 PROCESS MARKET ROUND"):
        game.run_market_logic()
        st.balloons()
        st.rerun()

# Final Scoring
if game.game_over:
    st.divider()
    st.header("🏆 Final Standings")
    final_scores = game.get_final_scores()
    st.table(final_scores.style.format({"Final_Share": "{:.2%}", "Price": "${:,.0f}", "Score": "{:.4f}"}))
