import streamlit as st
import pandas as pd

# ==========================================
# 1. CORE BUSINESS LOGIC (Revised for Dashboard)
# ==========================================
class Company:
    def __init__(self, name):
        self.name = name
        self.cash = 15000000
        self.is_bankrupt = False
        self.loss_penalty = False
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
        active = False
        for start in self.factory_effects:
            if current_round >= start:
                mult *= 1.1
                active = True
        return mult, active

    def get_current_pe(self):
        # Base PE 10 + Extra from Software. 
        # (Loss penalty -2 is usually applied at end-game, but we can display it here too)
        pe = 10 + self.extra_pe
        if self.current_loss_streak >= 2:
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
        round_results = []
        
        # 1. Calculate Weighted Inputs
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

        s_low = sum(w_low.values())
        s_high = sum(w_high.values())

        # 2. Process Performance
        temp_list = []
        for name in self.teams:
            comp = self.companies[name]
            if comp.is_bankrupt:
                temp_list.append({
                    'Name': name, 'Low Share': 0, 'High Share': 0, 'Total Share': 0,
                    'Profit': 0, 'Cash': comp.cash, 'Current PE': 0, 'Factory Active': "N/A", 'Price': 0
                })
                continue

            # Shares
            l_share = w_low[name]/s_low if s_low > 0 else 0.25
            h_share = w_high[name]/s_high if s_high > 0 else 0.25
            total_share = (l_share * low_market + h_share * high_market) / 100000
            
            # Profit
            u_l, u_h = comp.get_unit_profit(self.current_round)
            gross = (l_share * low_market * u_l) + (h_share * high_market * u_h)
            d = self.round_decisions[name]
            cost = (3000000 if d['vi']=='Manufacturing' else 0) + (1500000 if d['vi']=='Software' else 0) + (5000000 if d['build_factory'] else 0)
            
            # Apply Investment for FUTURE rounds
            if d['vi'] == 'Manufacturing': comp.mfg_effects.append((self.current_round + 1, self.current_round + 2, 100, 200))
            if d['vi'] == 'Software': 
                comp.soft_effects.append((self.current_round + 1, 5, 10))
                comp.extra_pe += 1
            if d['build_factory']: comp.factory_effects.append(self.current_round + 2)

            net = gross - cost
            comp.cash += net
            comp.last_round_profit = net
            comp.last_total_share = total_share
            
            # PE & Loss Streak
            if net < 0:
                comp.current_loss_streak += 1
                if comp.current_loss_streak >= 2: comp.loss_penalty = True
            else: comp.current_loss_streak = 0
            
            if comp.cash < 0: comp.is_bankrupt = True
            
            _, factory_active = comp.get_multiplier(self.current_round)
            current_pe = comp.get_current_pe()

            temp_list.append({
                'Name': name,
                'Low Share': l_share,
                'High Share': h_share,
                'Total Share': total_share,
                'Profit': net,
                'Cash': comp.cash,
                'Current PE': current_pe,
                'Factory Active': "Yes" if factory_active else "No",
                'Price': net * current_pe # Estimated Share Price
            })

        # 3. Calculate Rankings
        df_round = pd.DataFrame(temp_list)
        df_round['Share Rank'] = df_round['Total Share'].rank(ascending=False, method='min').astype(int)
        df_round['Price Rank'] = df_round['Price'].rank(ascending=False, method='min').astype(int)
        
        self.history.append(df_round)
        self.submitted_teams = set()
        self.round_decisions = {}
        
        if self.current_round >= 4: self.game_over = True
        else: self.current_round += 1
        return True

# ==========================================
# 2. MULTIPLAYER INTERFACE
# ==========================================

@st.cache_resource
def get_shared_game():
    return SimulationEngine()

game = get_shared_game()

st.set_page_config(page_title="Automotive Strategy Dashboard", layout="wide")
st.title("🚗 Automotive Strategy Simulation Dashboard")

# User Selection
st.sidebar.title("Login Portal")
user_team = st.sidebar.selectbox("Select Your Team", ["--- Select ---"] + game.teams)

if user_team == "--- Select ---":
    st.info("👋 Welcome! Please select your team in the sidebar to participate.")
    st.stop()

if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

# --- HEADER STATUS ---
st.subheader(f"Game Status: Round {game.current_round} / 4")
cols = st.columns(4)
for i, t in enumerate(game.teams):
    status = "✅ Ready" if t in game.submitted_teams else "⏳ Thinking..."
    if game.companies[t].is_bankrupt: status = "💀 BANKRUPT"
    cols[i].metric(t, status)

# --- DECISION FORM ---
if not game.game_over:
    if user_team not in game.submitted_teams and not game.companies[user_team].is_bankrupt:
        with st.form("decision_entry"):
            st.write(f"### 📊 Round {game.current_round} Strategy: {user_team}")
            l_ratio = st.slider("Target Low-End Market Share (%)", 0.0, 1.0, 0.5, 0.05)
            vi = st.selectbox("Vertical Integration (VI)", ["None", "Manufacturing", "Software"])
            fac = st.checkbox("Build Factory (-5,000,000)")
            if st.form_submit_button("Submit Strategy"):
                game.submit_team_decision(user_team, {"low_ratio": l_ratio, "high_ratio": 1.0 - l_ratio, "vi": vi, "build_factory": fac})
                st.rerun()
    elif user_team in game.submitted_teams:
        st.success("Waiting for other teams to finalize their strategies...")

# --- DASHBOARD DISPLAY ---
if game.history:
    st.divider()
    latest_report = game.history[-1]
    
    st.header(f"📈 Round {len(game.history)} Performance Dashboard")
    
    # Organizing columns for readability
    # Market Performance
    st.subheader("1. Market & Ranking Performance")
    market_df = latest_report[['Name', 'Low Share', 'High Share', 'Total Share', 'Share Rank', 'Price Rank']]
    st.table(market_df.style.format({
        'Low Share': '{:.2%}', 'High Share': '{:.2%}', 'Total Share': '{:.2%}'
    }))

    # Financial & Capital Performance
    st.subheader("2. Financial & Capital Market Results")
    finance_df = latest_report[['Name', 'Profit', 'Cash', 'Current PE', 'Factory Active']]
    st.table(finance_df.style.format({
        'Profit': '${:,.0f}', 'Cash': '${:,.0f}', 'Current PE': '{:.1f}'
    }))

# Admin Trigger
if len(game.submitted_teams) == 4 and not game.game_over:
    if st.button("🏁 ALL TEAMS SUBMITTED: CALCULATE ROUND RESULTS"):
        game.run_market_logic()
        st.rerun()

# End Game Final Result
if game.game_over:
    st.divider()
    st.header("🏆 FINAL CHAMPIONSHIP STANDINGS")
    final_df = game.history[-1].sort_values('Price Rank')
    st.balloons()
    st.dataframe(final_df, use_container_width=True)
    if st.sidebar.button("Reset Global Game"):
        st.cache_resource.clear()
        st.rerun()
