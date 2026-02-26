import streamlit as st
import pandas as pd
import time

# ==========================================
# 1. CORE BUSINESS LOGIC
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

    def get_multiplier_data(self, current_round):
        mult, active_from_past = 1.0, False
        for start in self.factory_effects:
            if current_round >= start:
                mult *= 1.1
                active_from_past = True
        return mult, active_from_past

    def get_current_pe(self):
        pe = 10 + self.extra_pe
        if self.current_loss_streak >= 2: pe -= 2
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
        
        w_low, w_high = {}, {}
        for name in self.teams:
            comp = self.companies[name]
            if comp.is_bankrupt:
                w_low[name], w_high[name] = 0, 0
            else:
                d = self.round_decisions[name]
                m, _ = comp.get_multiplier_data(self.current_round)
                w_low[name] = d['low_ratio'] * m
                w_high[name] = d['high_ratio'] * m

        s_low, s_high = sum(w_low.values()), sum(w_high.values())

        for name in self.teams:
            comp = self.companies[name]
            if comp.is_bankrupt:
                round_results.append({'Name': name, 'Profit_t': 0, 'Cash_t': comp.cash, 'Total Share': 0, 'Status': 'Bankrupt', 'Low Share': 0, 'High Share': 0, 'PE': 0, 'Factory': 'N/A', 'Est Price': 0})
                continue

            # 先算当轮竞争份额
            new_l_share = w_low[name]/s_low if s_low > 0 else 0.25
            new_h_share = w_high[name]/s_high if s_high > 0 else 0.25

            # 简单惯性：保留上一轮的一部分
            retain = 0.6  # 惯性强度：0.6~0.7 更像真实，0.4~0.5 更像游戏
            l_share = retain * comp.prev_low_share + (1-retain) * new_l_share
            h_share = retain * comp.prev_high_share + (1-retain) * new_h_share

            u_l, u_h = comp.get_unit_profit(self.current_round)
            gross = (l_share * low_market * u_l) + (h_share * high_market * u_h)
            
            d = self.round_decisions[name]
            cost = (3000000 if d['vi']=='Manufacturing' else 0) + (1500000 if d['vi']=='Software' else 0) + (5000000 if d['build_factory'] else 0)
            
            # FACTORY LOGIC: Show "Yes" if built now OR if active from the past
            _, fac_active_from_past = comp.get_multiplier_data(self.current_round)
            fac_display = "Yes" if (d['build_factory'] or fac_active_from_past) else "No"

            # Investment scheduling (Profit/Capacity timing remains unchanged)
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
            
            curr_pe = comp.get_current_pe()

            round_results.append({
                'Name': name, 'Profit_t': net, 'Cash_t': comp.cash, 'Total Share': comp.last_total_share, 
                'Low Share': l_share, 'High Share': h_share, 'PE': curr_pe, 'Factory': fac_display, 'Est Price': net * curr_pe
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
            pe = max(5, 10 + c.extra_pe - (2 if c.loss_penalty else 0))
            price = 0 if c.is_bankrupt else c.last_round_profit * pe
            final_list.append({'Name': name, 'Final_Share': c.last_total_share, 'Price': price})
        df = pd.DataFrame(final_list)
        ms, mp = df['Final_Share'].max(), df['Price'].max()
        df['Score'] = 0.5*(df['Final_Share']/(ms if ms>0 else 1)) + 0.5*(df['Price']/(mp if mp>0 else 1))
        return df.sort_values('Score', ascending=False)

# ==========================================
# 2. SHARED DATA DEPLOYMENT
# ==========================================
@st.cache_resource
def get_shared_game(): return SimulationEngine()
game = get_shared_game()

# ==========================================
# 3. MULTIPLAYER UI
# ==========================================
st.set_page_config(page_title="Multiplayer Strategy Sim", layout="wide")
st.title("🚗 Global Automotive Strategy Simulation")

st.sidebar.title("Player Portal")
user_team = st.sidebar.selectbox("Identify Your Team", ["--- Select ---", "Team 1", "Team 2", "Team 3", "Team 4"])
if user_team == "--- Select ---":
    st.warning("Please select your team in the sidebar to start.")
    st.stop()

if st.sidebar.button("🔄 Refresh Game Status"): st.rerun()

st.subheader(f"Status: Round {game.current_round} / 4")
cols = st.columns(4)
for i, t in enumerate(game.teams):
    status = "✅ Submitted" if t in game.submitted_teams else "⏳ Waiting..."
    if game.companies[t].is_bankrupt: status = "💀 Bankrupt"
    cols[i].metric(t, status)

st.divider()

if not game.game_over:
    if user_team in game.submitted_teams:
        st.success(f"Strategy for {user_team} sent. Waiting for others...")
    elif game.companies[user_team].is_bankrupt:
        st.error("Your company is bankrupt.")
    else:
        with st.form("decision_form"):
            st.write(f"### 📝 {user_team} Strategy Entry")
            l_ratio = st.slider("Low-End Market Focus (%)", 0.0, 1.0, 0.5, 0.05)
            vi = st.selectbox("Vertical Integration Investment", ["None", "Manufacturing", "Software"])
            fac = st.checkbox("Build Factory (-5,000,000)")
            if st.form_submit_button("Submit Strategy to Server"):
                game.submit_team_decision(user_team, {"low_ratio": l_ratio, "high_ratio": 1.0 - l_ratio, "vi": vi, "build_factory": fac})
                st.rerun()

if len(game.submitted_teams) == 4:
    if st.button("🚀 Calculate Round Results"):
        if game.run_market_logic():
            st.balloons()
            st.rerun()

if game.history:
    st.write("## 📊 Round Results Dashboard")
    for i, rep in enumerate(reversed(game.history)):
        st.write(f"**Round {len(game.history) - i} Performance**")
        cols_to_show = ['Name', 'Low Share', 'High Share', 'Total Share', 'Profit_t', 'Cash_t', 'PE', 'Factory', 'Share Rank', 'Price Rank']
        st.table(rep[cols_to_show].style.format({
            "Low Share": "{:.2%}", "High Share": "{:.2%}", "Total Share": "{:.2%}",
            "Profit_t": "{:,.0f}", "Cash_t": "{:,.0f}", "PE": "{:.1f}"
        }))

if game.game_over:
    st.header("🏆 Final Results")
    final = game.get_final_scores()
    st.table(final.style.format({"Final_Share": "{:.2%}", "Price": "{:,.2f}", "Score": "{:.4f}"}))
    if st.sidebar.button("Reset Entire Global Game"):
        st.cache_resource.clear()
        st.rerun()
