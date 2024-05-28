from datetime import date
import hmac

import polars as pl

import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title='budget', page_icon=':japanese_goblin:')
st.write('# :japan: the japan with a plan :japanese_goblin:')

def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            st.session_state["password_correct"] = False

    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password.
    st.text_input(
        "password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    return False


if not check_password():
    st.stop()  # Do not continue if check_password is not True.

# --- after login ---

today = date.today()

conn = st.connection('gsheets', type=GSheetsConnection)

df = conn.read(ttl=0)
plan = pl.from_pandas(df).with_columns(pl.col('paychecks').str.to_date('%Y/%m/%d'))

pay = st.secrets['pay']

past_paychecks = (
    plan
    .filter(pl.col('paychecks') <= today)
)

if not past_paychecks.is_empty():
    current_paycheck = past_paychecks['paychecks'].max()
    cp_fd_lo = (past_paychecks.select(pl.col('lo_fd').filter(pl.col('paychecks') == current_paycheck))).item()
    cp_food_lo = (past_paychecks.select(pl.col('lo_food').filter(pl.col('paychecks') == current_paycheck))).item()
    cp_extras_lo = (past_paychecks.select(pl.col('lo_extras').filter(pl.col('paychecks') == current_paycheck))).item()
    total_los = (past_paychecks.select(pl.col('lo_rt').filter(pl.col('paychecks') == current_paycheck))).item()

    nz_utils = past_paychecks.filter(pl.col('utils') > .001)

    if not nz_utils.is_empty():
        avg_utils = nz_utils.select(pl.col('utils')).mean().item()
        avg_utils_str = f'avg utils :electric_plug:: {avg_utils}'
    else:
        avg_utils_str = 'no utils yet'

    on_track = total_los + (plan.select(pl.col('running_total_b')).max()).item()

    st.markdown(
        f"""
            current paycheck :money_with_wings:: `{current_paycheck.strftime("%B/%d/%Y")}`  
            left over :dollar: (current paycheck):  
            >fd:chart:: {cp_fd_lo:.2f}  
            >food:hamburger:: {cp_food_lo:.2f}  
            >extras:pray:: {cp_extras_lo:.2f}  

            {avg_utils_str}  

            total left over :moneybag: to date: **{total_los:,.2f}**  
            on track to save :muscle: by dec 12: **{on_track:,.2f}**  
        """
    )

    with st.form(key='spend_form'):
        st.write('enter spends below:')
        fd_spend = st.number_input('fanduel', value=0)
        food_spend = st.number_input('food', value=0)
        extras_spend = st.number_input('extras', value=0)
        utils_spend = st.number_input('utils', value=0)
        submit = st.form_submit_button('submit')

    if submit:
        total_spend = fd_spend + food_spend + extras_spend + utils_spend
        if fd_spend != 0 or food_spend != 0 or extras_spend != 0 or utils_spend != 0:
            st.write(f'total spend: {total_spend}')
            plan = (
                plan
                .with_columns(
                    pl.when(
                        pl.col('paychecks') == current_paycheck
                    )
                    .then(pl.col('fd') + fd_spend)
                    .otherwise(pl.col('fd'))
                    .alias('fd'),
                    pl.when(
                        pl.col('paychecks') == current_paycheck
                    )
                    .then(pl.col('food') + food_spend)
                    .otherwise(pl.col('food'))
                    .alias('food'),
                    pl.when(
                        pl.col('paychecks') == current_paycheck
                    )
                    .then(pl.col('extras') + extras_spend)
                    .otherwise(pl.col('extras'))
                    .alias('extras'),
                    pl.when(
                        pl.col('paychecks') == current_paycheck
                    )
                    .then(pl.col('utils') + utils_spend)
                    .otherwise(pl.col('utils'))
                    .alias('utils')
                )
                .with_columns(
                    (pay - (pl.col('reg costs') + pl.col('fd') + pl.col('food') + pl.col('extras') + pl.col('utils'))).alias('net'),
                    (pl.col('fd_b') - pl.col('fd')).alias('lo_fd'),
                    (pl.col('food_b') - pl.col('food')).alias('lo_food'),
                    (pl.col('extras_b') - pl.col('extras')).alias('lo_extras'),
                    (pl.col('utils_b') - pl.col('utils')).alias('lo_utils'),
                )
                .with_columns(
                    pl.col('net').cum_sum().alias('total'),
                    (pl.col('lo_fd') + pl.col('lo_food') + pl.col('lo_extras') + pl.col('lo_utils')).alias('lo_total')
                )
                .with_columns(
                    pl.col('lo_total').cum_sum().alias('lo_rt')
                )
            )
            conn.update(data=plan.to_pandas())
            st.rerun()
        else:
            st.write('no spends')
else:
    st.write('no current paycheck, come back after may 30')
