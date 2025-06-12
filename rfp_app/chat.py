# Functions related to chat and OpenAI interactions
import os
import streamlit as st
from openai import OpenAI


def get_env_api_key():
    """Read API key from .env or environment variables"""
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.strip() and line.startswith('OPENAI_API_KEY=') and not line.startswith('#'):
                    return line.split('=', 1)[1].strip()
    except Exception:
        pass
    return os.getenv('OPENAI_API_KEY', '')


openai_api_key = get_env_api_key()


def debug_api_key(key: str, source: str) -> None:
    """Log masked API keys when DEBUG_API_KEY environment variable is true."""
    if os.getenv("DEBUG_API_KEY", "").lower() == "true":
        if key:
            masked = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "***"
            print(f"DEBUG - API KEY from {source}: {masked}, Length: {len(key)}")
        else:
            print(f"DEBUG - API KEY from {source}: Not set or empty")


def get_openai_client() -> OpenAI:
    api_key = st.session_state.get('openai_api_key') or openai_api_key
    debug_api_key(api_key, 'get_openai_client')
    if not api_key:
        raise ValueError('No OpenAI API key found. Please provide one in the settings.')
    return OpenAI(api_key=api_key)


def test_api_key(api_key: str):
    if not api_key:
        return False, 'No API key provided'
    try:
        client = OpenAI(api_key=api_key)
        client.chat.completions.create(
            model='gpt-4o',
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5,
        )
        return True, 'API key is valid'
    except Exception as e:
        msg = str(e)
        if 'quota' in msg.lower() or 'billing' in msg.lower():
            return False, f'API key has quota issues: {msg}'
        return False, f'Invalid API key: {msg}'


def generate_response(prompt: str) -> str:
    """Generate a chat completion using the current RFP context."""
    try:
        client = get_openai_client()

        # Build RFP context with key information so the model can answer
        rfp_context = ''
        if st.session_state.get('current_rfp'):
            rfp = st.session_state.current_rfp
            rfp_context = 'RFP Information:\n'
            if 'customer' in rfp:
                rfp_context += f"Customer: {rfp['customer']}\n\n"
            if 'scope' in rfp:
                rfp_context += f"Scope: {rfp['scope']}\n\n"

            # Summarise tasks for better context
            if rfp.get('tasks'):
                rfp_context += 'Major Tasks:\n'
                for task in rfp['tasks'][:5]:
                    title = task.get('title', 'Task')
                    desc = task.get('description', 'No description')
                    page = task.get('page', 'N/A')
                    rfp_context += f"- {title}: {desc} (Page {page})\n"
                if len(rfp['tasks']) > 5:
                    rfp_context += f"... and {len(rfp['tasks']) - 5} more tasks\n"
                rfp_context += '\n'

            # Summarise requirements by category
            if rfp.get('requirements'):
                rfp_context += 'Key Requirements:\n'
                reqs_by_category = {}
                for req in rfp['requirements']:
                    cat = req.get('category', 'General')
                    reqs_by_category.setdefault(cat, []).append(req)
                for category, reqs in reqs_by_category.items():
                    rfp_context += f"{category}:\n"
                    for req in reqs[:3]:
                        desc = req.get('description', 'No description')
                        page = req.get('page', 'N/A')
                        rfp_context += f"- {desc} (Page {page})\n"
                    if len(reqs) > 3:
                        rfp_context += f"... and {len(reqs) - 3} more requirements in this category\n"
                rfp_context += '\n'

            # Summarise key dates
            if rfp.get('dates'):
                rfp_context += 'Key Dates:\n'
                for date in rfp['dates'][:5]:
                    event = date.get('event', 'Event')
                    date_str = date.get('date', 'No date')
                    page = date.get('page', 'N/A')
                    rfp_context += f"- {event}: {date_str} (Page {page})\n"
                if len(rfp['dates']) > 5:
                    rfp_context += f"... and {len(rfp['dates']) - 5} more dates\n"

        # Base system message
        messages = [{"role": "system", "content": st.session_state.get('system_message', '')}]
        if rfp_context:
            messages.append({"role": "system", "content": f"Current RFP: {st.session_state.get('rfp_name', '')}\n\n{rfp_context}"})

        # Add previous conversation
        for msg in st.session_state.get('messages', [])[-10:]:
            messages.append({"role": msg['role'], "content": msg['content']})

        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model='gpt-4o',
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )

        return response.choices[0].message.content
    except Exception as e:
        return f"I apologize, but I encountered an error: {str(e)}"


def display_chat_interface():
    """Render a simple chat interface within Streamlit."""
    st.markdown('<h3>Ask about this RFP</h3>', unsafe_allow_html=True)

    if 'messages' not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m['role'], avatar='🤖' if m['role'] == 'assistant' else None):
            st.markdown(m['content'])

    if st.session_state.get('openai_api_key') and (prompt := st.chat_input('Ask me about this RFP...')):
        st.session_state.messages.append({'role': 'user', 'content': prompt})
        with st.chat_message('user'):
            st.markdown(prompt)
        with st.chat_message('assistant', avatar='🤖'):
            with st.spinner('Analyzing RFP data...'):
                response = generate_response(prompt)
                st.markdown(response)
        st.session_state.messages.append({'role': 'assistant', 'content': response})
        st.rerun()
    elif not st.session_state.get('openai_api_key'):
        st.warning('Please enter your OpenAI API key in the sidebar to enable chat functionality.')
