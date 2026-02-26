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
        self.mfg_effects = []   # (start, end, low_bonus, high_bonus)
        self.soft_effects = []  # (start, low_bonus, high_bonus)
        self.factory_effects = [] # [start_round]
        self.last_round_profit = 0
        self.last_total_share = 0

    def get_unit_profit(self, current_round):
        """Calculates current unit profit with bonuses."""
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
        """Calculates factory multiplier and active status."""
        mult, active = 1.0, False
        for start in self.factory_effects:
            if current_round >= start:
                mult *= 1.1
                active = True
        return mult, active

    def get_current_pe(self):
        """Calculates PE based on Software and Loss Penalty."""
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
        
        # 1. Calculate Inputs with Multipliers
        w_low, w_high = {}, {}
        for name in self.teams:
            comp = self.companies[name]
            if comp.is_bankrupt:
                w_low[name], w_high[name] = 0, 0
            else:
                d = self.round_decisions[name]
                m, _ = comp.get_multiplier(self.current_round)
                w_low[name] = d['low_ratio'] * m
                w_high[name] = d['high_ratio'] * m

        s_low, s_high = sum(w_low.values()), sum(w_high.values())

        # 2. Process Round Performance
        for name in self.teams:
            comp = self.companies[name]
            if comp.is_bankrupt:
                temp_list.append({
                    'Team': name, 'Low-End Share': 0.0, 'High-End Share': 0.0, 'Total Market Share': 0.0,
                    'Round Profit': 0, 'Cash Balance': comp.cash, 'Current PE': 0, 'Factory Active': "Bankrupt", 'Share Price': 0
                })
                continue

            # Market Share
            l_share = w_low[name]/s_low if s_low > 0 else 0.25
            h_share = w_high[name]/s_high if s_high > 0 else 0.25
            total_share = (l_share * low_market + h_share * high_market) / 100000
            
            # Unit Profits & Gross
            u_l, u_h = comp.get_unit_profit(self.current_round)
            gross = (l_share * low_market * u_l) + (h_share * high_market * u_h)
            
            # Costs & Decision Implementation
            d = self.round_decisions[name]
            cost = (3000000 if d['vi']=='Manufacturing' else 0) + (1500000 if d['vi']=='Software' else 0) + (5000000 if d['build_factory'] else 0)
            
            if d['vi'] == 'Manufacturing': comp.mfg_effects.append((self.current_round + 1, self.current_round + 2, 100, 200))
            if d['vi'] == 'Software': 
                comp.soft_effects.append((self.current_round + 1, 5, 10))
                comp.extra_pe += 1
            if d['build_factory']: comp.factory_effects.append(self.current_round + 2)

            net = gross - cost
            comp.cash += net
            comp.last_round_profit = net
            comp.last_total_share = total_share
            
            # Loss Streaks
            if net < 0:
                comp.current_loss_streak += 1
                if comp.current_loss_streak >= 2: comp.loss_penalty_triggered = True
            else: comp.current_loss_streak = 0
            
            if comp.cash < 0: comp.is_bankrupt = True
            
            # Dashboard Metadata
            _, fac_on = comp.get_multiplier(self.current_round)
            c_pe = comp.get_current_pe()

            temp_list.append({
                'Team': name,
                'Low-End Share': l_share,
                'High-End Share': h_share,
                'Total Market Share': total_share,
                'Round Profit': net,
                'Cash Balance': comp.cash,
                'Current PE': c_pe,
                'Factory Active': "Yes" if fac_on else "No",
                'Share Price': net * c_pe
            })

        # 3. Finalize Round Dataframe & Rankings
        df_round = pd.DataFrame(temp_list)
        df_round['Market Share Rank'] = df_round['Total Market Share'].rank(ascending=False, method='min').astype(int)
        df_round['Stock Price Rank'] = df_round['Share Price'].rank(ascending=False, method='min').astype(int)
        
        self.history.append(df_round)
        self.submitted_teams, self.round_decisions = set(), {}
        if self.current_round >= 4: self.game_over = True
        else: self.current_round += 1
        return True

# ==========================================
# 2. STREAMLIT MULTIPLAYER UI
# ==========================================

@st.cache_resource
def get_shared_game():
    return SimulationEngine()

game = get_shared_game()

st.set_page_config(page_title="Auto Strategy Sim", layout="wide")
st.title("🚗 Global Automotive Strategy Simulation")

# Sidebar
st.sidebar.title("Player Portal")
user_team = st.sidebar.selectbox("Identify Your Team", ["--- Select ---"] + game.teams)
if st.sidebar.button("🔄 Sync/Refresh Data"): st.rerun()

if user_team == "--- Select ---":
    st.info("👋 Welcome! Please select your team in the sidebar to enter the simulation.")
    st.stop()

# Progress Metrics
st.subheader(f"Status: Round {game.current_round} / 4")
status_cols = st.columns(4)
for i, t in enumerate(game.teams):
    status_text = "✅ Ready" if t in game.submitted_teams else "⏳ Thinking..."
    if game.companies[t].is_bankrupt: status_text = "💀 BANKRUPT"
    status_cols[i].metric(t, status_text)

st.divider()

# Strategy Input Form
if not game.game_over:
    if user_team in game.submitted_teams:
        st.success(f"Strategy for {user_team} submitted. Waiting for others...")
    elif game.companies[user_team].is_bankrupt:
        st.error("Your company is bankrupt. Access restricted.")
    else:
        with st.form("decision_form"):
            st.write(f"### 📝 Round {game.current_round} Input: {user_team}")
            l_ratio = st.slider("Low-End Market Focus (%)", 0.0, 1.0, 0.5, 0.05)
            vi = st.selectbox("Vertical Integration (VI)", ["None", "Manufacturing", "Software"])
            fac = st.checkbox("Build New Factory (-5,000,000)")
            
            if st.form_submit_button("Submit Strategy"):
                game.submit_team_decision(user_team, {
                    "low_ratio": l_ratio, "high_ratio": 1.0 - l_ratio, 
                    "vi": vi, "build_factory": fac
                })
                st.rerun()

# Execution Trigger
if len(game.submitted_teams) == 4 and not game.game_over:
    st.warning("All teams have submitted! Ready to process market data.")
    if st.button("🚀 CALCULATE ROUND RESULTS"):
        if game.run_market_logic():
            st.balloons()
            st.rerun()

# --- REVISED DASHBOARD SECTION ---
if game.history:
    st.divider()
    latest = game.history[-1]
    
    st.header(f"📈 Round {len(game.history)} Official Dashboard")
    
    # Requirement: Market Share, Profit, Cash, PE, Factory, and Rankings
    display_cols = [
        'Team', 
        'Low-End Share', 'High-End Share', 'Total Market Share', 
        'Round Profit', 'Cash Balance', 
        'Current PE', 'Factory Active', 'Share Price',
        'Market Share Rank', 'Stock Price Rank'
    ]
    
    st.table(latest[display_cols].style.format({
        'Low-End Share': '{:.2%}', 
        'High-End Share': '{:.2%}', 
        'Total Market Share': '{:.2%}',
        'Round Profit': '${:,.0f}', 
        'Cash Balance': '${:,.0f}',
        'Current PE': '{:.1f}',
        'Share Price': '${:,.2f}'
    }))

# Game Over Logic
if game.game_over:
    st.divider()
    st.header("🏆 Final Championship Results")
    final_results = game.history[-1].copy()
    
    # Calculate Game Score: 50% Share Ratio, 50% Price Ratio
    max_s = final_results['Total Market Share'].max()
    max_p = final_results['Share Price'].max()
    final_results['Final Score'] = 0.5*(final_results['Total Market Share']/(max_s if max_s>0 else 1)) + \
                                  0.5*(final_results['Share Price']/(max_p if max_p>0 else 1))
    
    st.dataframe(final_results.sort_values('Final Score', ascending=False), use_container_width=True)
    
    winner = final_results.sort_values('Final Score', ascending=False).iloc[0]['Team']
    st.success(f"### The Global Champion is: {winner}!")

    if st.sidebar.button("Reset Global Game"):
        st.cache_resource.clear()
        st.rerun()
