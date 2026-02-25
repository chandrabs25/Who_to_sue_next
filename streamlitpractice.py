import streamlit as st

st.title("The Counter Paradox: Solved")

# 1. Initialize the state if it doesn't exist
if 'count' not in st.session_state:
    st.session_state.count = 0

# 2. Update the state when button is clicked


name = st.text_input("What's your name?")
with st.sidebar:
    st.header("Settings")
    if name:
        st.write(f"Hello, {name}!")
    if st.button("Add 1"):
        st.session_state.count += 1
st.write(f"Current count: {st.session_state.count}")