import streamlit as st
import pandas as pd

# ==========================================
# 1. CORE BUSINESS LOGIC
# ==========================================
class Company:
    def __init__(self, name):
        self.name = name
        self.cash = 15000000
        self.is_bankrupt = False
        self.ever_had_consecutive_loss = False
        self.last_round_net_profit = 0
        self.extra_pe = 0
        self.mfg_effects = []   
        self.soft_effects = []  
        self.factory_effects = [] 
        
        # INERTIA: Round 0 shares at 25%
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
                mult *= 1.1
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
        self.decision_history = [] # NEW: Tracks all raw inputs
        self.round_decisions = {} 
        self.submitted_teams = set()
        self.game_over = False
        self.alpha = 0.6 

    def submit_team_decision(self, team_name, dec):
        self.round_decisions[team_name] = dec
        self.submitted_teams.add(team_name)

    def run_market_logic(self):
        if len(self.submitted_teams) < 4:
            return False
        
        low_market, high_market = 80000, 20000
        round_results = []
        
        # 1. Record Decisions for Audit
        for name, d in self.round_decisions.items():
            self.decision_history.append({
                'Round': self.current_round,
                'Team': name,
                'Low %': f"{d['low_ratio']:.0%}",
                'High %': f"{d['high_ratio']:.0%}",
                'VI': d['vi'],
                'Factory': "Yes" if d['build_factory'] else "No"
            })
        
        # 2. Market Share Logic
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

        s_low_total = sum(w_low.values())
        s_high_total = sum(w_high.values())

        # 3. Process Financials
        for name in self.teams:
            comp = self.companies[name]
            if comp.is_bankrupt:
                round_results.append({
                    'Team': name, 'Op Profit': 0.0, 'Net Profit': 0.0, 'Cash Balance': comp.cash, 
                    'Total Share': 0.0, 'Low Share': 0.0, 'High Share': 0.0, 
                    'PE': 0.0, 'Factory': 'Bankrupt', 'Est Price': 0.0
                })
                continue

            new_l = w_low[name]/s_low_total if s_low_total > 0 else 0.25
            new_h = w_high[name]/s_high_total if s_high_total > 0 else 0.25
            act_l = (self.alpha * comp.prev_low_share) + ((1 - self.alpha) * new_l)
            act_h = (self.alpha * comp.prev_high_share) + ((1 - self.alpha) * new_h)
            comp.prev_low_share, comp.prev_high_share = act_l, act_h
            
            u_l, u_h = comp.get_unit_profit(self.current_round)
            op_profit = (act_l * low_market * u_l) + (act_h * high_market * u_h)
            
            d = self.round_decisions[name]
            inv_cost = (3000000 if d['vi']=='Manufacturing' else 0) + \
                       (1500000 if d['vi']=='Software' else 0) + \
                       (5000000 if d['build_factory'] else 0)
            
            net_profit = op_profit - inv_cost
            comp.cash += net_profit
            
            if comp.last_round_net_profit < 0 and net_profit < 0:
                comp.ever_had_consecutive_loss = True
            comp.last_round_net_profit = net_profit

            est_price = max(0.0, op_profit * comp.get_display_pe())

            if d['vi'] == 'Manufacturing': comp.mfg_effects.append((self.current_round + 1, self.current_round + 2, 100, 200))
            if d['vi'] == 'Software': 
                comp.soft_effects.append((self.current_round + 1, 5, 10))
                comp.extra_pe += 1
            if d['build_factory']: comp.factory_effects.append(self.current_round + 2)

            if comp.cash < 0: comp.is_bankrupt = True
            
            _, active_past = comp.get_multiplier_data(self.current_round)
            fac_display = "Yes" if (d['build_factory'] or active_past) else "No"

            round_results.append({
                'Team': name, 'Op Profit': op_profit, 'Net Profit': net_profit, 
                'Cash Balance': comp.cash, 'Total Share': (act_l * low_market + act_h * high_market) / 100000, 
                'Low Share': act_l, 'High Share': act_h, 
                'PE': comp.get_display_pe(), 'Factory': fac_display, 'Est Price': est_price
            })

        df = pd.DataFrame(round_results)
        df['Share Rank'] = df['Total Share'].rank(ascending=False, method='min').astype(int)
        df['Price Rank'] = df['Est Price'].rank(ascending=False, method='min').astype(int)
        
        self.history.append(df)
        self.submitted_teams, self.round_decisions = set(), {}
        if self.current_round >= 4: self.game_over = True
        else: self.current_round += 1
        return True

    def get_final_scores(self):
        final_list = []
        for name in self.teams:
            c = self.companies[name]
            if c.is_bankrupt:
                final_list.append({'Team': name, 'Final_Share': 0, 'Price': 0, 'Score': 0})
                continue
            final_pe = max(5, 10 + c.extra_pe - (2 if c.ever_had_consecutive_loss else 0))
            last_op = self.history[-1][self.history[-1]['Team'] == name]['Op Profit'].values[0]
            final_price = max(0.0, last_op * final_pe)
            final_list.append({
                'Team': name, 
                'Final_Share': self.history[-1][self.history[-1]['Team'] == name]['Total Share'].values[0], 
                'Price': final_price
            })
        df = pd.DataFrame(final_list)
        ms, mp = df['Final_Share'].max(), df['Price'].max()
        df['Score'] = 0.5*(df['Final_Share']/(ms if ms>0 else 1)) + 0.5*(df['Price']/(mp if mp>0 else 1))
        return df.sort_values('Score', ascending=False)

# --- UI LOGIC ---
@st.cache_resource
def get_shared_game(): return SimulationEngine()
game = get_shared_game()

st.set_page_config(page_title="Simulation Dashboard", layout="wide")
st.title("🚗 Automotive Strategic Simulation")

# Sidebar
st.sidebar.title("Simulation Control")
role = st.sidebar.selectbox("Select Role", ["--- Select ---", "Teacher/Observer", "Team 1", "Team 2", "Team 3", "Team 4"])
if role == "Teacher/Observer":
    st.sidebar.warning("🛠️ Admin Authority")
    if st.sidebar.button("🚨 RESET ALL DATA"):
        st.cache_resource.clear()
        st.rerun()
if st.sidebar.button("🔄 Sync Screen"): st.rerun()

if role == "--- Select ---":
    st.info("Select your role in the sidebar.")
    st.stop()

# Header Status
st.subheader(f"Round {game.current_round} Progress")
s_cols = st.columns(4)
for i, t in enumerate(game.teams):
    status = "✅ Ready" if t in game.submitted_teams else "⏳ Thinking"
    if game.companies[t].is_bankrupt: status = "💀 Bankrupt"
    s_cols[i].metric(t, status)

# Charts Section
if game.history:
    st.divider()
    c1, c2 = st.columns(2)
    
    # Prepare Data for Charts
    # Each list starts with 0.25 (Initial Round 0 Share)
    low_chart_data = pd.DataFrame({t: [0.25] + [round_df[round_df['Team'] == t]['Low Share'].values[0] for round_df in game.history] for t in game.teams})
    high_chart_data = pd.DataFrame({t: [0.25] + [round_df[round_df['Team'] == t]['High Share'].values[0] for round_df in game.history] for t in game.teams})
    
    with c1:
        st.write("### 📉 Low-End Market Share Trend")
        st.line_chart(low_chart_data)
    with c2:
        st.write("### 📈 High-End Market Share Trend")
        st.line_chart(high_chart_data)

# Dashboard Section
if game.history:
    st.write(f"## 📊 Round {len(game.history)} Official Results")
    latest = game.history[-1]
    cols_to_show = ['Team', 'Low Share', 'High Share', 'Total Share', 'Op Profit', 'Net Profit', 'Cash Balance', 'PE', 'Factory', 'Est Price', 'Share Rank', 'Price Rank']
    st.table(latest[cols_to_show].style.format({
        "Low Share": "{:.2%}", "High Share": "{:.2%}", "Total Share": "{:.2%}", 
        "Op Profit": "${:,.0f}", "Net Profit": "${:,.0f}", "Cash Balance": "${:,.0f}", 
        "PE": "{:.1f}", "Est Price": "${:,.0f}"
    }))

# Team Input
if role.startswith("Team") and not game.game_over:
    if role in game.submitted_teams:
        st.success(f"Strategy for {role} locked.")
    elif game.companies[role].is_bankrupt:
        st.error("Bankrupt.")
    else:
        with st.form("input"):
            st.write(f"### {role} Input (R{game.current_round})")
            l = st.slider("Low-End allocation", 0.0, 1.0, 0.5, 0.05)
            v = st.selectbox("VI Investment", ["None", "Manufacturing", "Software"])
            f = st.checkbox("Build Factory")
            if st.form_submit_button("Submit"):
                game.submit_team_decision(role, {"low_ratio": l, "high_ratio": 1.0 - l, "vi": v, "build_factory": f})
                st.rerun()

# Teacher Calculation
if len(game.submitted_teams) == 4 and not game.game_over:
    if role == "Teacher/Observer":
        if st.button("🚀 EXECUTE CALCULATIONS"):
            game.run_market_logic()
            st.balloons()
            st.rerun()

# Final Summary Page
if game.game_over:
    st.divider()
    st.header("🏆 Final Review & Championship Standing")
    
    # 1. Final Scoring
    st.write("### 🥇 Final Standings")
    st.table(game.get_final_scores().style.format({"Final_Share": "{:.2%}", "Price": "${:,.0f}", "Score": "{:.4f}"}))
    
    # 2. Complete Decision Audit
    st.write("### 📝 Strategic Audit (Full Decision History)")
    audit_df = pd.DataFrame(game.decision_history)
    # Sort for easier reading by Team then Round
    audit_df = audit_df.sort_values(['Team', 'Round'])
    st.dataframe(audit_df, use_container_width=True)
