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
        mult, active = 1.0, False
        for start in self.factory_effects:
            if current_round >= start:
                mult *= 1.1
                active = True
        return mult, active

    def get_current_pe(self):
        pe = 10 + self.extra_pe
        if self.current_loss_streak >= 2 or self.loss_penalty_triggered:
            pe -= 2
        return max(5, pe)

class SimulationEngine:
    def __init__(self):
        self.teams = ["Team 1", "Team 2", "Team 3", "Team 4"]
        self.companies = {name: Company(name) for name in self.teams}
        self.current_round = 1
        self.history = [] 
        self.round_decisions = {} 
        self.submitted_teams = set()
        self.game_over = False

    def submit_team_decision(self, team_name, dec):
        self.round_decisions[team_name] = dec
        self.submitted_teams.add(team_name)

    def run_market_logic(self):
        if len(self.submitted_teams) < 4:
            return False
        
        low_market, high_market = 80000, 20000
        temp_list = []
        
        # 1. Calculate weighted inputs
        w_low, w_high = {}, {}
        for name in self.teams:
            comp = self.companies[name]
            if comp.is_bankrupt:
                w_low[name], w_high[name] = 0.0, 0.0
            else:
                d = self.round_decisions[name]
                m, _ = comp.get_multiplier(self.current_round)
                w_low[name] = float(d['low_ratio'] * m)
                w_high[name] = float(d['high_ratio'] * m)

        s_low, s_high = sum(w_low.values()), sum(w_high.values())

        # 2. Process metrics
        for name in self.teams:
            comp = self.companies[name]
            
            # Initial values for everyone to avoid KeyError
            row = {
                'Team': name, 'Low-End Share': 0.0, 'High-End Share': 0.0, 'Total Market Share': 0.0,
                'Round Profit': 0.0, 'Cash Balance': float(comp.cash), 'Current PE': 0.0, 
                'Factory Active': "Bankrupt", 'Share Price': 0.0
            }

            if not comp.is_bankrupt:
                l_share = w_low[name]/s_low if s_low > 0 else 0.25
                h_share = w_high[name]/s_high if s_high > 0 else 0.25
                total_share = (l_share * low_market + h_share * high_market) / 100000
                
                u_l, u_h = comp.get_unit_profit(self.current_round)
                gross = (l_share * low_market * u_l) + (h_share * high_market * u_h)
                
                d = self.round_decisions[name]
                cost = (3000000 if d['vi']=='Manufacturing' else 0) + (1500000 if d['vi']=='Software' else 0) + (5000000 if d['build_factory'] else 0)
                
                # Apply future effects
                if d['vi'] == 'Manufacturing': comp.mfg_effects.append((self.current_round + 1, self.current_round + 2, 100, 200))
                if d['vi'] == 'Software': 
                    comp.soft_effects.append((self.current_round + 1, 5, 10))
                    comp.extra_pe += 1
                if d['build_factory']: comp.factory_effects.append(self.current_round + 2)

                net = gross - cost
                comp.cash += net
                comp.last_round_profit = net
                comp.last_total_share = total_share
                
                if net < 0:
                    comp.current_loss_streak += 1
                    if comp.current_loss_streak >= 2: comp.loss_penalty_triggered = True
                else: comp.current_loss_streak = 0
                
                if comp.cash < 0: comp.is_bankrupt = True
                
                _, fac_on = comp.get_multiplier(self.current_round)
                c_pe = comp.get_current_pe()

                row.update({
                    'Low-End Share': l_share, 'High-End Share': h_share, 'Total Market Share': total_share,
                    'Round Profit': net, 'Cash Balance': float(comp.cash),
                    'Current PE': float(c_pe), 'Factory Active': "Yes" if fac_on else "No",
                    'Share Price': float(net * c_pe)
                })

            temp_list.append(row)

        df_round = pd.DataFrame(temp_list)
        
        # Safe Ranking (even if data is 0)
        df_round['Market Share Rank'] = df_round['Total Market Share'].rank(ascending=False, method='min').astype(int)
        df_round['Stock Price Rank'] = df_round['Share Price'].rank(ascending=False, method='min').astype(int)
        
        self.history.append(df_round)
        self.submitted_teams, self.round_decisions = set(), {}
        if self.current_round >= 4: self.game_over = True
        else: self.current_round += 1
        return True

# ==========================================
# 2. UI LOGIC
# ==========================================

@st.cache_resource
def get_shared_game():
    return SimulationEngine()

game = get_shared_game()

st.set_page_config(page_title="Strategic Management Sim", layout="wide")
st.title("🚗 Automotive Strategy Simulation")

# Sidebar
st.sidebar.title("Player Portal")
user_team = st.sidebar.selectbox("Identify Your Team", ["--- Select ---"] + game.teams)
if st.sidebar.button("🔄 Sync Game Status"): st.rerun()

if user_team == "--- Select ---":
    st.info("👋 Please select your team in the sidebar.")
    st.stop()

# --- HEADER ---
st.subheader(f"Current Phase: Strategy Entry for Round {game.current_round}")
cols = st.columns(4)
for i, t in enumerate(game.teams):
    status = "✅ Submitted" if t in game.submitted_teams else "⏳ Thinking..."
    if game.companies[t].is_bankrupt: status = "💀 BANKRUPT"
    cols[i].metric(t, status)

# --- INPUT ---
if not game.game_over:
    if user_team in game.submitted_teams:
        st.success("Strategy locked. Waiting for others...")
    elif game.companies[user_team].is_bankrupt:
        st.error("Company Bankrupt.")
    else:
        with st.form("decision_form"):
            st.write(f"### 📝 {user_team}: Input Strategy (Round {game.current_round})")
            l_ratio = st.slider("Low-End Market Focus (%)", 0.0, 1.0, 0.5, 0.05)
            vi = st.selectbox("Vertical Integration", ["None", "Manufacturing", "Software"])
            fac = st.checkbox("Build Factory (-5,000,000)")
            if st.form_submit_button("Submit Strategy"):
                game.submit_team_decision(user_team, {"low_ratio": l_ratio, "high_ratio": 1.0 - l_ratio, "vi": vi, "build_factory": fac})
                st.rerun()

# --- CALCULATION TRIGGER ---
if len(game.submitted_teams) == 4 and not game.game_over:
    if st.button("🚀 CALCULATE RESULTS"):
        if game.run_market_logic():
            st.balloons()
            st.rerun()

# --- DYNAMIC DASHBOARD (SAFE RENDER) ---
if game.history:
    st.divider()
    latest_report = game.history[-1]
    
    st.header(f"📈 Results for Round {len(game.history)}")
    
    display_cols = [
        'Team', 'Low-End Share', 'High-End Share', 'Total Market Share', 
        'Round Profit', 'Cash Balance', 'Current PE', 'Factory Active', 
        'Share Price', 'Market Share Rank', 'Stock Price Rank'
    ]
    
    # Final check to ensure all columns exist before showing
    available_cols = [c for c in display_cols if c in latest_report.columns]
    
    st.table(latest_report[available_cols].style.format({
        'Low-End Share': '{:.2%}', 'High-End Share': '{:.2%}', 'Total Market Share': '{:.2%}',
        'Round Profit': '${:,.0f}', 'Cash Balance': '${:,.0f}',
        'Current PE': '{:.1f}', 'Share Price': '${:,.2f}'
    }))

# --- FINAL CHAMPIONSHIP ---
if game.game_over:
    st.divider()
    st.header("🏆 Final Championship Ranking")
    final_df = game.history[-1].copy()
    max_s, max_p = final_df['Total Market Share'].max(), final_df['Share Price'].max()
    final_df['Final Score'] = 0.5*(final_df['Total Market Share']/(max_s if max_s>0 else 1)) + \
                               0.5*(final_df['Share Price']/(max_p if max_p>0 else 1))
    st.dataframe(final_df.sort_values('Final Score', ascending=False), use_container_width=True)
    if st.sidebar.button("Reset Simulation"):
        st.cache_resource.clear()
        st.rerun()
