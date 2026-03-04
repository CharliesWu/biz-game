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
        self.mfg_effects = []   # Format: (start_round, end_round, low_bonus, high_bonus)
        self.soft_effects = []  # Format: (start_round, low_bonus, high_bonus)
        self.factory_effects = [] # Format: [start_round_active]
        
        # Market Inertia: Initial share for Round 0 is assumed at 25%
        self.prev_low_share = 0.25
        self.prev_high_share = 0.25

    def get_unit_profit(self, current_round):
        """Calculates adjusted unit profit based on active investments."""
        low_p, high_p = 500, 1000
        # Manufacturing: Rewards are +50 for Low and +100 for High
        for start, end, l_b, h_b in self.mfg_effects:
            if start <= current_round <= end:
                low_p += l_b
                high_p += h_b
        # Software: Rewards are +5 for Low and +10 for High (starts from next round)
        for start, l_b, h_b in self.soft_effects:
            if current_round >= start:
                low_p += l_b
                high_p += h_b
        return low_p, high_p

    def get_multiplier_data(self, current_round):
        """Checks if factory multiplier (1.1x) is currently active."""
        mult, active_from_past = 1.0, False
        for start in self.factory_effects:
            if current_round >= start:
                mult *= 1.1
                active_from_past = True
        return mult, active_from_past

    def get_display_pe(self):
        """Returns PE with floor of 5."""
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
        self.alpha = 0.6 # Smoothing factor for market inertia

    def submit_team_decision(self, team_name, dec):
        self.round_decisions[team_name] = dec
        self.submitted_teams.add(team_name)

    def run_market_logic(self):
        """Executes the round calculation logic."""
        if len(self.submitted_teams) < 4:
            return False
        
        low_market, high_market = 80000, 20000
        round_results = []
        
        # Calculate active teams for default share distribution if total investment is 0
        active_count = sum(1 for c in self.companies.values() if not c.is_bankrupt)
        default_share = 1.0 / active_count if active_count > 0 else 0.25

        # 1. Audit Trail: Record raw decisions
        for name, d in self.round_decisions.items():
            self.decision_history.append({
                'Round': self.current_round,
                'Team': name,
                'Low %': f"{d['low_ratio']:.0%}",
                'High %': f"{d['high_ratio']:.0%}",
                'VI': d['vi'],
                'Factory': "Build" if d['build_factory'] else "No"
            })
        
        # 2. Market Intensity (Weighted Input)
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

        # 3. Financial and Market Processing
        for name in self.teams:
            comp = self.companies[name]
            if comp.is_bankrupt:
                round_results.append({
                    'Team': name, 'Op Profit': 0.0, 'Net Profit': 0.0, 'Cash Balance': comp.cash, 
                    'Total Share': 0.0, 'Low Share': 0.0, 'High Share': 0.0, 
                    'PE': 0.0, 'Factory': 'Bankrupt', 'Est Price': 0.0
                })
                continue

            # Share calculation with 0.6 Alpha (Inertia)
            new_l = w_low[name]/s_low_total if s_low_total > 0 else default_share
            new_h = w_high[name]/s_high_total if s_high_total > 0 else default_share
            
            act_l = (self.alpha * comp.prev_low_share) + ((1 - self.alpha) * new_l)
            act_h = (self.alpha * comp.prev_high_share) + ((1 - self.alpha) * new_h)
            
            # Save actual share as history for the next round's inertia
            comp.prev_low_share, comp.prev_high_share = act_l, act_h
            
            # Calculate Profit (Units * Unit Profit)
            u_l, u_h = comp.get_unit_profit(self.current_round)
            op_profit = (act_l * low_market * u_l) + (act_h * high_market * u_h)
            
            # Decision costs
            d = self.round_decisions[name]
            inv_cost = (3000000 if d['vi']=='Manufacturing' else 0) + \
                       (1500000 if d['vi']=='Software' else 0) + \
                       (5000000 if d['build_factory'] else 0)
            
            # Process investment effects
            # 1. Software: PE increase is applied IMMEDIATELY for the current round's price
            if d['vi'] == 'Software': 
                comp.extra_pe += 1
                comp.soft_effects.append((self.current_round + 1, 5, 10))
            
            # 2. Manufacturing: Effects start T+1 and last 2 rounds
            if d['vi'] == 'Manufacturing': 
                comp.mfg_effects.append((self.current_round + 1, self.current_round + 2, 50, 100))
            
            # 3. Factory: Multiplier starts at T+2
            if d['build_factory']: 
                comp.factory_effects.append(self.current_round + 2)

            # Net Profit and Cash Update
            net_profit = op_profit - inv_cost
            comp.cash += net_profit
            
            # Check for consecutive loss penalty (PE -2)
            if comp.last_round_net_profit < 0 and net_profit < 0:
                comp.ever_had_consecutive_loss = True
            comp.last_round_net_profit = net_profit

            # Estimated Price = Op Profit * Current PE
            est_price = max(0.0, op_profit * comp.get_display_pe())

            # Bankruptcy Check
            if comp.cash < 0: comp.is_bankrupt = True
            
            # Factory Display Logic: Show "Yes" if currently building OR if effect is active
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
        """Calculates final scores based on 50% Market Share and 50% Share Price."""
        final_list = []
        for name in self.teams:
            c = self.companies[name]
            if c.is_bankrupt:
                final_list.append({'Team': name, 'Final_Share': 0, 'Price': 0, 'Score': 0})
                continue
            
            # Apply consecutive loss penalty to final PE
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
        
        # Normalize scores against the leaders
        df['Score'] = 0.5*(df['Final_Share']/(ms if ms>0 else 1)) + 0.5*(df['Price']/(mp if mp>0 else 1))
        return df.sort_values('Score', ascending=False)

# ==========================================
# 2. UI LOGIC (STREAMLIT)
# ==========================================
@st.cache_resource
def get_shared_game(): return SimulationEngine()
game = get_shared_game()

st.set_page_config(page_title="Strategic Simulation", layout="wide")
st.title("🚗 Automotive Strategic Simulation Dashboard")

# Sidebar for Reset and Role Selection
st.sidebar.title("Sim Control")
role = st.sidebar.selectbox("Select Role", ["--- Select ---", "Teacher/Observer", "Team 1", "Team 2", "Team 3", "Team 4"])
if role == "Teacher/Observer":
    if st.sidebar.button("🚨 RESET GAME"):
        st.cache_resource.clear()
        st.rerun()
if st.sidebar.button("🔄 Refresh Data"): st.rerun()

if role == "--- Select ---":
    st.info("Please select a role from the sidebar to begin.")
    st.stop()

# Progress Status
st.subheader(f"Round {game.current_round} Progress")
s_cols = st.columns(4)
for i, t in enumerate(game.teams):
    status = "✅ Ready" if t in game.submitted_teams else "⏳ Thinking"
    if game.companies[t].is_bankrupt: status = "💀 Bankrupt"
    s_cols[i].metric(t, status)

# Trend Charts
if game.history:
    st.divider()
    c1, c2 = st.columns(2)
    # Generate chart data starting from Round 0 (25% baseline)
    low_chart = pd.DataFrame({t: [0.25] + [r[r['Team'] == t]['Low Share'].values[0] for r in game.history] for t in game.teams})
    high_chart = pd.DataFrame({t: [0.25] + [r[r['Team'] == t]['High Share'].values[0] for r in game.history] for t in game.teams})
    with c1:
        st.write("### 📉 Low-End Share Trend")
        st.line_chart(low_chart)
    with c2:
        st.write("### 📈 High-End Share Trend")
        st.line_chart(high_chart)

# Result Tables
if game.history:
    st.write(f"## 📊 Latest Results (Round {len(game.history)})")
    latest = game.history[-1]
    format_dict = {
        "Low Share": "{:.2%}", "High Share": "{:.2%}", "Total Share": "{:.2%}", 
        "Op Profit": "${:,.0f}", "Net Profit": "${:,.0f}", "Cash Balance": "${:,.0f}", 
        "PE": "{:.1f}", "Est Price": "${:,.0f}"
    }
    st.table(latest.style.format(format_dict))

# Decision Input Form
if role.startswith("Team") and not game.game_over:
    if role in game.submitted_teams:
        st.success(f"Strategy for {role} has been locked.")
    elif game.companies[role].is_bankrupt:
        st.error(f"{role} is bankrupt and cannot participate.")
    else:
        with st.form("decision_form"):
            st.write(f"### Strategy Input: {role} (R{game.current_round})")
            l_alloc = st.slider("Low-End Resource Allocation %", 0.0, 1.0, 0.5, 0.05)
            vi_choice = st.selectbox("Vertical Integration Investment", ["None", "Manufacturing", "Software"])
            build_f = st.checkbox("Build New Factory ($5M)")
            if st.form_submit_button("Submit Strategy"):
                game.submit_team_decision(role, {"low_ratio": l_alloc, "high_ratio": 1.0 - l_alloc, "vi": vi_choice, "build_factory": build_f})
                st.rerun()

# Teacher Processing Logic
if len(game.submitted_teams) == 4 and not game.game_over:
    if role == "Teacher/Observer":
        st.warning("All teams have submitted their strategies. Proceed with market calculation?")
        if st.button("🚀 PROCESS MARKET ROUND"):
            game.run_market_logic()
            st.balloons()
            st.rerun()

# Final Standings and Audit Trail
if game.game_over:
    st.divider()
    st.header("🏆 Final Championship Standings")
    st.table(game.get_final_scores().style.format({"Final_Share": "{:.2%}", "Price": "${:,.0f}", "Score": "{:.4f}"}))
    st.write("### 📝 Decision Audit Trail (Full History)")
    audit_df = pd.DataFrame(game.decision_history).sort_values(['Team', 'Round'])
    st.dataframe(audit_df, use_container_width=True)
