import streamlit as st
import pandas as pd
import streamlit.components.v1 as components

# ==========================================
# 1. 核心业务逻辑
# ==========================================
class Company:
    def __init__(self, name):
        self.name = name
        self.cash = 7000000 
        self.is_bankrupt = False
        self.ever_had_consecutive_loss = False
        self.last_round_profit = 0 
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

        # 记录决策用于审计
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
            if comp.last_round_profit < 0 and net_profit < 0: 
                comp.ever_had_consecutive_loss = True
            
            comp.cash += net_profit
            comp.last_round_profit = net_profit

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
            mc = 0 if c.is_bankrupt else c.last_round_profit * pe
            final_list.append({'Team': name, 'Final_Share': 0.0, 'Market Cap': mc})
        
        for i, entry in enumerate(final_list):
            name = entry['Team']
            if not self.companies[name].is_bankrupt:
                entry['Final_Share'] = self.history[-1][self.history[-1]['Team'] == name]['Total Share'].values[0]

        df = pd.DataFrame(final_list)
        ms, mmc = df['Final_Share'].max(), df['Market Cap'].max()
        df['Score'] = 0.5*(df['Final_Share']/(ms if ms>0 else 1)) + 0.5*(df['Market Cap']/(mmc if mmc>0 else 1))
        return df.sort_values('Score', ascending=False)

# ==========================================
# 2. UI 逻辑与视觉特效
# ==========================================

# 烟花特效代码 (JavaScript)
fireworks_js = """
<script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.5.1/dist/confetti.browser.min.js"></script>
<script>
    var duration = 5 * 1000;
    var animationEnd = Date.now() + duration;
    var defaults = { startVelocity: 30, spread: 360, ticks: 60, zIndex: 0 };

    function randomInRange(min, max) {
      return Math.random() * (max - min) + min;
    }

    var interval = setInterval(function() {
      var timeLeft = animationEnd - Date.now();

      if (timeLeft <= 0) {
        return clearInterval(interval);
      }

      var particleCount = 50 * (timeLeft / duration);
      confetti(Object.assign({}, defaults, { particleCount, origin: { x: randomInRange(0.1, 0.3), y: Math.random() - 0.2 } }));
      confetti(Object.assign({}, defaults, { particleCount, origin: { x: randomInRange(0.7, 0.9), y: Math.random() - 0.2 } }));
    }, 250);
</script>
"""

@st.cache_resource
def get_shared_game(): return SimulationEngine()
game = get_shared_game()

st.set_page_config(page_title="Strategic Simulation", layout="wide")
st.title("🚗 Automotive Strategic Simulation Dashboard")

def style_results(df):
    def color_ranks(val):
        if val == 1: return 'background-color: #FFD700; color: black; font-weight: bold' # 金
        if val == 2: return 'background-color: #C0C0C0; color: black; font-weight: bold' # 银
        if val == 3: return 'background-color: #CD7F32; color: white; font-weight: bold' # 铜
        if val == 4: return 'background-color: #E1F5FE; color: #01579B; font-weight: bold' # 浅蓝
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

# 侧边栏
st.sidebar.title("Sim Control")
role = st.sidebar.selectbox("Select Role", ["--- Select ---", "Teacher/Observer", "Team 1", "Team 2", "Team 3", "Team 4"])

st.sidebar.markdown("---")
if role == "Teacher/Observer":
    st.sidebar.subheader("🚨 Danger Zone")
    confirm_reset = st.sidebar.checkbox("Double check to enable reset")
    if st.sidebar.button("RESET ALL GAME DATA", disabled=not confirm_reset):
        st.cache_resource.clear()
        if 'celebrated' in st.session_state: del st.session_state['celebrated']
        st.rerun()

if st.sidebar.button("🔄 Sync Screen"): st.rerun()

if role == "--- Select ---":
    st.info("Please select your role in the sidebar.")
    st.stop()

# 进度状态
st.subheader(f"Round {game.current_round} Progress")
s_cols = st.columns(4)
for i, t in enumerate(game.teams):
    status = "✅ Ready" if t in game.submitted_teams else "⏳ Thinking"
    if game.companies[t].is_bankrupt: status = "💀 Bankrupt"
    s_cols[i].metric(t, status)

# 趋势图展示 (如果有历史数据)
if game.history:
    st.divider()
    c1, c2 = st.columns(2)
    low_chart_data = pd.DataFrame({t: [0.25] + [round_df[round_df['Team'] == t]['Low Share'].values[0] for round_df in game.history] for t in game.teams})
    high_chart_data = pd.DataFrame({t: [0.25] + [round_df[round_df['Team'] == t]['High Share'].values[0] for round_df in game.history] for t in game.teams})
    with c1:
        st.write("### 📉 Low-End Market Share Trend")
        st.line_chart(low_chart_data)
    with c2:
        st.write("### 📈 High-End Market Share Trend")
        st.line_chart(high_chart_data)

# 结果看板
if game.history:
    st.divider()
    latest = game.history[-1]
    st.write(f"## 📊 Round {len(game.history)} Official Results")
    st.dataframe(style_results(latest), hide_index=True, use_container_width=True)

# 团队决策输入
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

# 老师执行计算
if len(game.submitted_teams) == 4 and not game.game_over and role == "Teacher/Observer":
    if st.button("🚀 PROCESS MARKET ROUND"):
        game.run_market_logic()
        st.balloons()
        st.rerun()

# 最终回顾页面 (只有游戏结束才显示)
if game.game_over:
    # 庆祝效果：烟花 + 气球
    if 'celebrated' not in st.session_state:
        st.balloons()
        components.html(fireworks_js, height=0)
        st.session_state['celebrated'] = True

    st.divider()
    st.header("🏆 Final Review & Championship Standing")
    
    # 最终排名
    final_scores = game.get_final_scores()
    st.write("### 🥇 Final Standings")
    st.dataframe(final_scores.style.format({"Final_Share": "{:.2%}", "Market Cap": "${:,.0f}", "Score": "{:.4f}"}), hide_index=True, use_container_width=True)
    
    # 决策审计表
    st.write("### 📝 Strategic Audit (Full Decision History)")
    audit_df = pd.DataFrame(game.decision_history)
    st.dataframe(audit_df.sort_values(['Team', 'Round']), hide_index=True, use_container_width=True)
