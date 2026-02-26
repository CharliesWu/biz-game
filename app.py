import streamlit as st
import pandas as pd
import time

# ==========================================
# 1. CORE BUSINESS LOGIC (Same as before)
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
        for start in self.factory_effects:
            if current_round >= start:
                mult *= 1.1
        return mult

class SimulationEngine:
    def __init__(self):
        self.teams = ["Team 1", "Team 2", "Team 3", "Team 4"]
        self.companies = {name: Company(name) for name in self.teams}
        self.current_round = 1
        self.history = []
        self.round_decisions = {} # Temporary storage for current round
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
        
        # Calculate Weighted Inputs
        w_low = {}
        w_high = {}
        for name in self.teams:
            comp = self.companies[name]
            if comp.is_bankrupt:
                w_low[name], w_high[name] = 0, 0
            else:
                d = self.round_decisions[name]
                m = comp.get_multiplier(self.current_round)
                w_low[name] = d['low_ratio'] * m
                w_high[name] = d['high_ratio'] * m

        s_low = sum(w_low.values())
        s_high = sum(w_high.values())

        # Process Profits
        for name in self.teams:
            comp = self.companies[name]
            if comp.is_bankrupt:
                round_results.append({'Name': name, 'Profit': 0, 'Cash': comp.cash, 'Total Share': 0, 'Status': 'Bankrupt'})
                continue

            l_share = w_low[name]/s_low if s_low > 0 else 0.25
            h_share = w_high[name]/s_high if s_high > 0 else 0.25
            
            u_l, u_h = comp.get_unit_profit(self.current_round)
            gross = (l_share * low_market * u_l) + (h_share * high_market * u_h)
            
            d = self.round_decisions[name]
            cost = (3000000 if d['vi']=='Manufacturing' else 0) + (1500000 if d['vi']=='Software' else 0) + (5000000 if d['build_factory'] else 0)
            
            # Apply Investment Effects
            if d['vi'] == 'Manufacturing': comp.mfg_effects.append((self.current_round + 1, self.current_round + 2, 100, 200))
            if d['vi'] == 'Software': 
                comp.soft_effects.append((self.current_round + 1, 5, 10))
                comp.extra_pe += 1
            if d['build_factory']: comp.factory_effects.append(self.current_round + 2)

            net = gross - cost
            comp.cash += net
            comp.last_round_profit = net
            comp.last_total_share = (l_share * low_market + h_share * high_market) / 100000
            
            if net < 0:
                comp.current_loss_streak += 1
                if comp.current_loss_streak >= 2: comp.loss_penalty = True
            else: comp.current_loss_streak = 0
            
            if comp.cash < 0: comp.is_bankrupt = True
            
            round_results.append({'Name': name, 'Profit': net, 'Cash': comp.cash, 'Total Share': comp.last_total_share, 'Status': 'Active' if not comp.is_bankrupt else 'Bankrupt'})

        self.history.append(pd.DataFrame(round_results))
        self.submitted_teams = set()
        self.round_decisions = {}
        
        if self.current_round >= 4:
            self.game_over = True
        else:
            self.current_round += 1
        return True

    def get_final_scores(self):
        final_list = []
        for name in self.teams:
            c = self.companies[name]
            pe = max(5, 10 + c.extra_pe - (2 if c.loss_penalty else 0))
            price = 0 if c.is_bankrupt else c.last_round_profit * pe
            final_list.append({'Name': name, 'Final_Share': c.last_total_share, 'Price': price})
        
        df = pd.DataFrame(final_list)
        ms, mp = df['Final_Share'].max(), df['Price'].max()
        df['Score'] = 0.5*(df['Final_Share']/(ms if ms>0 else 1)) + 0.5*(df['Price']/(mp if mp>0 else 1))
        return df.sort_values('Score', ascending=False)

# ==========================================
# 2. SHARED DATA DEPLOYMENT (The Multiplayer "Brain")
# ==========================================

@st.cache_resource
def get_shared_game():
    return SimulationEngine()

game = get_shared_game()

# ==========================================
# 3. MULTIPLAYER UI
# ==========================================

st.set_page_config(page_title="Multiplayer Strategy Sim", layout="wide")
st.title("🚗 Global Automotive Strategy Simulation")

# Top Menu: Identify User
st.sidebar.title("Player Portal")
user_team = st.sidebar.selectbox("Identify Your Team", ["--- Select ---", "Team 1", "Team 2", "Team 3", "Team 4"])

if user_team == "--- Select ---":
    st.warning("Please select your team in the sidebar to start.")
    st.stop()

# Auto-refresh button (Streamlit needs manual triggers to pull data from other players)
if st.sidebar.button("🔄 Refresh Game Status"):
    st.rerun()

# --- THE WAITING ROOM ---
st.subheader(f"Status: Round {game.current_round} / 4")
cols = st.columns(4)
for i, t in enumerate(game.teams):
    status = "✅ Submitted" if t in game.submitted_teams else "⏳ Waiting..."
    if game.companies[t].is_bankrupt: status = "💀 Bankrupt"
    cols[i].metric(t, status)

st.divider()

# --- INPUT SECTION ---
if not game.game_over:
    if user_team in game.submitted_teams:
        st.success(f"Strategy for {user_team} has been sent. Waiting for other teams...")
    elif game.companies[user_team].is_bankrupt:
        st.error("Your company is bankrupt. You can no longer make decisions.")
    else:
        with st.form("decision_form"):
            st.write(f"### 📝 {user_team} Strategy Entry")
            l_ratio = st.slider("Low-End Market Focus (%)", 0.0, 1.0, 0.5, 0.05)
            vi = st.selectbox("Vertical Integration Investment", ["None", "Manufacturing", "Software"])
            fac = st.checkbox("Build New Factory (-5,000,000)")
            
            if st.form_submit_button("Submit Strategy to Server"):
                game.submit_team_decision(user_team, {
                    "low_ratio": l_ratio, "high_ratio": 1.0 - l_ratio, 
                    "vi": vi, "build_factory": fac
                })
                st.rerun()

# --- ADMIN / CALCULATION SECTION ---
# In a real game, anyone can click this once it's 4/4, or you can password protect it.
if len(game.submitted_teams) == 4:
    st.info("All teams have submitted!")
    if st.button("🚀 Calculate Round Results"):
        if game.run_market_logic():
            st.balloons()
            st.rerun()

# --- RESULTS DISPLAY ---
if game.history:
    st.write("## 📊 Historical Reports")
    for i, rep in enumerate(reversed(game.history)):
        st.write(f"**Round {len(game.history) - i} Results**")
        st.table(rep.style.format({"Profit": "{:,.0f}", "Cash": "{:,.0f}", "Total Share": "{:.2%}"}))

if game.game_over:
    st.header("🏆 Final Results")
    final = game.get_final_scores()
    st.table(final.style.format({"Final_Share": "{:.2%}", "Price": "{:,.2f}", "Score": "{:.4f}"}))
    if st.sidebar.button("Reset Entire Global Game"):
        st.cache_resource.clear()
        st.rerun()
