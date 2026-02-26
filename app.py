import streamlit as st
import pandas as pd

# ==========================================
# 1. CORE BUSINESS LOGIC CLASSES
# ==========================================

class Company:
    """
    Represents a competing firm in the simulation.
    Tracks financial health, investment effects, and market performance.
    """
    def __init__(self, name):
        self.name = name
        self.cash = 15000000  # Initial Cash: 15,000,000
        self.is_bankrupt = False
        self.loss_penalty_triggered = False  # Track if consecutive loss PE penalty applies
        self.current_loss_streak = 0 
        
        self.extra_pe = 0  # Accumulated from Software Integration
        self.mfg_effects = []   # (start_round, end_round, low_bonus, high_bonus)
        self.soft_effects = []  # (start_round, low_bonus, high_bonus)
        self.factory_effects = [] # [list of start_rounds for multipliers]
        
        self.last_round_profit = 0
        self.last_total_share = 0

    def get_unit_profit(self, current_round):
        """Calculates current unit profit including bonuses from VI."""
        # Base: Low-End 500, High-End 1,000
        low_p, high_p = 500, 1000
        
        # Add Manufacturing bonuses (Active only in t+1 and t+2)
        for start, end, l_b, h_b in self.mfg_effects:
            if start <= current_round <= end:
                low_p += l_b
                high_p += h_b
        
        # Add Software bonuses (Persistent from t+1 onwards)
        for start, l_b, h_b in self.soft_effects:
            if current_round >= start:
                low_p += l_b
                high_p += h_b
        return low_p, high_p

    def get_multiplier(self, current_round):
        """Calculates the factory capacity multiplier (1.1x per factory)."""
        mult = 1.0
        # Factory effect starts at t+2
        for start in self.factory_effects:
            if current_round >= start:
                mult *= 1.1
        return mult

class Simulation:
    """
    Handles market share distribution, profit calculation, and bankruptcy.
    """
    def __init__(self, names):
        self.companies = {name: Company(name) for name in names}

    def execute_round(self, round_num, all_decisions):
        # Total Market Demand Constants
        low_market, high_market = 80000, 20000
        round_results = []
        
        # 1. CALCULATE WEIGHTED INPUTS (Applying Factory Multipliers)
        weighted_low = {}
        weighted_high = {}
        for name, comp in self.companies.items():
            if comp.is_bankrupt:
                weighted_low[name], weighted_high[name] = 0, 0
                continue
            
            dec = all_decisions[name]
            m = comp.get_multiplier(round_num)
            weighted_low[name] = dec['low_ratio'] * m
            weighted_high[name] = dec['high_ratio'] * m

        sum_low = sum(weighted_low.values())
        sum_high = sum(weighted_high.values())
        
        # 2. CALCULATE SALES, COSTS, AND PROFITS
        for name, comp in self.companies.items():
            if comp.is_bankrupt:
                round_results.append({
                    'Name': name, 'Profit': 0, 'Cash': comp.cash, 
                    'Total Share': 0, 'Status': 'Bankrupt'
                })
                continue

            # Market Share Calculation
            low_share = weighted_low[name] / sum_low if sum_low > 0 else 1/len(self.companies)
            high_share = weighted_high[name] / sum_high if sum_high > 0 else 1/len(self.companies)
            
            sales_low = low_share * low_market
            sales_high = high_share * high_market
            
            # Unit Profit Calculation
            u_low, u_high = comp.get_unit_profit(round_num)
            gross_profit = (sales_low * u_low) + (sales_high * u_high)
            
            # Investment Cost Deduction
            dec = all_decisions[name]
            inv_cost = 0
            if dec['vi'] == 'Manufacturing':
                inv_cost += 3000000
                # Benefit: t+1 and t+2
                comp.mfg_effects.append((round_num + 1, round_num + 2, 100, 200))
            elif dec['vi'] == 'Software':
                inv_cost += 1500000
                # Benefit: t+1 onwards, PE +1
                comp.soft_effects.append((round_num + 1, 5, 10))
                comp.extra_pe += 1
            
            if dec['build_factory']:
                inv_cost += 5000000
                # Benefit: t+2 onwards
                comp.factory_effects.append(round_num + 2)
            
            # Update Financials
            net_profit = gross_profit - inv_cost
            comp.cash += net_profit
            comp.last_round_profit = net_profit
            comp.last_total_share = (sales_low + sales_high) / 100000
            
            # Check for Consecutive Losses (PE -2 Penalty)
            if net_profit < 0:
                comp.current_loss_streak += 1
                if comp.current_loss_streak >= 2:
                    comp.loss_penalty_triggered = True
            else:
                comp.current_loss_streak = 0
            
            # Bankruptcy Check
            if comp.cash < 0:
                comp.is_bankrupt = True
            
            round_results.append({
                'Name': name, 'Profit': net_profit, 'Cash': comp.cash, 
                'Total Share': comp.last_total_share, 'Status': 'Active' if not comp.is_bankrupt else 'Bankrupt'
            })
        return pd.DataFrame(round_results)

    def get_final_ranking(self):
        """Calculates final scores based on 50% Market Share and 50% Share Price."""
        final_data = []
        for name, comp in self.companies.items():
            if comp.is_bankrupt:
                final_data.append({'Name': name, 'Final_Share': 0, 'Price': 0})
                continue
            
            # Calculate Final PE
            final_pe = 10 + comp.extra_pe
            if comp.loss_penalty_triggered:
                final_pe -= 2
            final_pe = max(5, final_pe)  # PE Floor is 5
            
            # Share Price = EPS (Round 4 Profit) * PE
            price = comp.last_round_profit * final_pe
            final_data.append({'Name': name, 'Final_Share': comp.last_total_share, 'Price': price})
            
        df = pd.DataFrame(final_data)
        max_share = df['Final_Share'].max()
        max_price = df['Price'].max()
        
        # Score Formula: 0.5 * (Share / Max) + 0.5 * (Price / Max)
        df['Score'] = 0.5 * (df['Final_Share'] / (max_share if max_share > 0 else 1)) + \
                      0.5 * (df['Price'] / (max_price if max_price > 0 else 1))
        return df.sort_values(by='Score', ascending=False)

# ==========================================
# 2. STREAMLIT UI COMPONENTS
# ==========================================

st.set_page_config(page_title="Business Strategy Sim", layout="wide")
st.title("🚗 Automotive Market Strategy Simulator")

# Session State Initialization
if 'game_started' not in st.session_state:
    st.session_state.teams = ["Team 1", "Team 2", "Team 3", "Team 4"]
    st.session_state.game = Simulation(st.session_state.teams)
    st.session_state.current_round = 1
    st.session_state.history_reports = []
    st.session_state.game_over = False

# SIDEBAR: DECISION ENTRY
if not st.session_state.game_over:
    st.sidebar.header(f"Round {st.session_state.current_round} Decisions")
    
    current_decisions = {}
    for team in st.session_state.teams:
        st.sidebar.subheader(f"📍 {team}")
        comp_obj = st.session_state.game.companies[team]
        is_disabled = comp_obj.is_bankrupt
        
        # User Inputs
        low = st.sidebar.slider(f"{team}: Low-End Ratio", 0.0, 1.0, 0.5, 0.05, 
                               key=f"{team}_low_{st.session_state.current_round}",
                               disabled=is_disabled)
        high = 1.0 - low
        st.sidebar.caption(f"High-End Ratio: {high:.2f}")
        
        vi = st.sidebar.selectbox(f"{team}: Vertical Integration", ["None", "Manufacturing", "Software"], 
                                 key=f"{team}_vi_{st.session_state.current_round}",
                                 disabled=is_disabled)
        factory = st.sidebar.checkbox(f"{team}: Build Factory?", 
                                     key=f"{team}_fac_{st.session_state.current_round}",
                                     disabled=is_disabled)
        
        current_decisions[team] = {
            "low_ratio": low,
            "high_ratio": high,
            "vi": vi,
            "build_factory": factory
        }

    if st.sidebar.button("Submit Decisions & Calculate Round"):
        report = st.session_state.game.execute_round(st.session_state.current_round, current_decisions)
        st.session_state.history_reports.append(report)
        
        if st.session_state.current_round < 4:
            st.session_state.current_round += 1
        else:
            st.session_state.game_over = True
        st.rerun()

# MAIN INTERFACE: DISPLAY REPORTS
col1, col2 = st.columns([2, 1])

with col1:
    if st.session_state.history_reports:
        # Show reports in reverse order (newest first)
        for i, report in enumerate(reversed(st.session_state.history_reports)):
            r_num = len(st.session_state.history_reports) - i
            st.write(f"### Round {r_num} Performance Report")
            st.dataframe(report.style.format({
                "Profit": "{:,.0f}", 
                "Cash": "{:,.0f}", 
                "Total Share": "{:.2%}"
            }), use_container_width=True)
    else:
        st.info("💡 **Instructions:** Enter strategy ratios and investments in the sidebar, then click 'Submit Decisions'. Follow the 4-round market evolution.")

with col2:
    if st.session_state.game_over:
        st.balloons()
        st.success("### 🏁 Simulation Complete!")
        final_ranking = st.session_state.game.get_final_ranking()
        
        st.write("#### Final Leaderboard")
        st.dataframe(final_ranking.style.format({
            "Final_Share": "{:.2%}", 
            "Price": "{:,.2f}", 
            "Score": "{:.4f}"
        }), use_container_width=True)
        
        winner = final_ranking.iloc[0]['Name']
        st.header(f"🏆 Winner: {winner}")
        
        if st.button("Reset Game"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    else:
        st.write(f"### Progress: Round {st.session_state.current_round} / 4")
        st.metric("Total Market Demand", "100,000 Units")
        st.write("**Quick Guide:**")
        st.markdown("""
        - **Manufacturing**: -3M cost. +Profit in T+1, T+2.
        - **Software**: -1.5M cost. +Profit and +1 PE in T+1.
        - **Factory**: -5M cost. 1.1x capacity in T+2.
        - **Bankruptcy**: Occurs if Cash drops below 0.
        """)
