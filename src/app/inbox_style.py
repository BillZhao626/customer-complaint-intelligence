"""Light inbox styles, scoped to stable app keys and Streamlit test IDs."""
import streamlit as st


def apply():
    st.markdown('''<style>
    :root {--ink:#222436;--muted:#53586b;--line:#e5e3ed;--accent:#5949c5;}
    .stApp {background:#fff;color:var(--ink);}
    [data-testid="stHeader"] {height:0;background:transparent;}
    [data-testid="stToolbar"] {display:none;}
    .block-container {max-width:none;padding:1.15rem 1.5rem 1rem;}
    h1 {font-size:1.35rem!important;} h3 {font-size:1.08rem!important;padding:.2rem 0 .45rem!important;}
    [data-testid="stVerticalBlock"] {gap:.65rem;}
    [data-testid="stText"] {white-space:pre-wrap;overflow-wrap:anywhere;font-family:inherit;font-size:15px;line-height:1.65;}
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {color:var(--muted);font-size:13px;line-height:1.5;}
    [data-testid="stCaptionContainer"] {opacity:1!important;}
    [data-testid="stTextArea"] textarea {font-size:16px;line-height:1.6;background:#fff;color:var(--ink);}
    .brand {display:flex;align-items:center;justify-content:space-between;padding:0 0 .4rem;}
    .brand-title {display:flex;gap:10px;align-items:center;font-size:19px;font-weight:650;letter-spacing:.4px;}
    .brand-icon {background:#6556d8;color:white;border-radius:10px;padding:5px 9px;font-size:19px;}
    .brand-note {font-size:13px;color:var(--muted);}
    .pill {display:inline-block;padding:3px 9px;border-radius:7px;background:#f1efff;color:#5141b3;font-size:13px;}
    .stTabs [data-baseweb="tab-list"] {gap:1.5rem;border-bottom:1px solid var(--line);}
    .stTabs [data-baseweb="tab"] {font-size:.88rem;height:40px;}
    .stTabs [aria-selected="true"] {color:var(--accent);}
    .stTabs [data-baseweb="tab-highlight"] {background:var(--accent);}
    button[kind="primary"] {background:var(--accent);border-color:var(--accent);color:white;}
    button[kind="secondary"] {border-color:#e8e7ef;}
    [data-testid="stButton"] button {border-radius:9px;font-size:14px;}
    [data-testid="stAlertContainer"] {font-size:14px;}
    .st-key-inbox_pane {padding-right:14px;border-right:1px solid var(--line);}
    .st-key-inbox_pane [data-baseweb="select"] > div {padding-left:9px;padding-right:5px;font-size:13px;}
    .st-key-copilot_pane {padding-left:14px;border-left:1px solid var(--line);}
    .st-key-inbox_scroll {height:calc(100dvh - 385px)!important;min-height:220px;border:0!important;}
    .st-key-conversation {height:280px!important;min-height:180px;border:0!important;background:#fff;}
    .st-key-conversation_single {max-height:260px;overflow-y:auto;}
    .st-key-assistant_scroll {height:calc(100dvh - 240px)!important;min-height:270px;border:0!important;}
    .st-key-inbox_scroll [data-testid="stButton"] button {width:100%;text-align:left;justify-content:flex-start;border:0;padding:12px;background:#fff;}
    .st-key-inbox_scroll [data-testid="stButton"] button p {text-align:left;font-size:13px;line-height:1.5;margin-bottom:3px;}
    .st-key-inbox_scroll [data-testid="stButton"] button strong {font-size:14px;font-weight:600;}
    .st-key-inbox_scroll .st-key-selected_case button {background:#f0eeff;border-left:3px solid #7667df;}
    .st-key-inbox_scroll [data-testid="stButton"] button:hover {background:#f6f5fc;}
    .conversation-title {font-size:18px;font-weight:650;margin:3px 0 4px;}
    .message {max-width:94%;border-radius:13px;background:#f3f3f6;padding:13px 16px;margin:6px 0 10px;font-size:16px;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere;}
    .message.outgoing {margin-left:auto;background:#eeecfc;}
    .message-meta {font-size:13px;color:#53586b;margin-bottom:7px;white-space:normal;}
    .next-step {font-size:14px;color:#453b82;background:#f5f3ff;border-radius:8px;padding:10px 12px;line-height:1.5;}
    .st-key-composer {border:1px solid #e5e3ef;border-radius:12px;padding:12px 14px;box-shadow:0 4px 15px #30245b08;}
    .composer-heading {font-size:15px;font-weight:600;}
    .st-key-composer [data-testid="stTextArea"] label {display:none;}
    .st-key-composer textarea {border:0!important;}
    .st-key-suggestion_card {border-radius:13px;background:linear-gradient(125deg,#f0edff,#f8f0f7);padding:15px;}
    .st-key-suggestion_card [data-testid="stText"] {font-size:15px;line-height:1.65;}
    .section-label {font-size:13px;color:#56516b;margin:4px 0 7px;}
    .need {font-size:15px;font-weight:600;line-height:1.6;margin:4px 0 7px;}
    .st-key-region_switch {display:none;}
    @media (max-width:1100px) {
      .block-container {padding:1rem 1rem 0;}
      .st-key-composer {padding-bottom:10px;}
      .brand-note {display:none;}
      .st-key-region_switch {display:block;}
      .st-key-layout_inbox > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"],
      .st-key-layout_conversation > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"],
      .st-key-layout_copilot > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {flex-wrap:wrap;}
      [class*="st-key-layout_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {min-width:100%;}
      .st-key-layout_inbox > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:not(:nth-child(1)),
      .st-key-layout_conversation > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:not(:nth-child(2)),
      .st-key-layout_copilot > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:not(:nth-child(3)) {display:none;}
      .st-key-inbox_pane,.st-key-copilot_pane {border:0;padding:0;}
      .st-key-conversation {height:280px!important;min-height:180px;}
      .st-key-inbox_scroll {height:calc(100dvh - 440px)!important;}
      .st-key-assistant_scroll {height:auto!important;max-height:none;}
    }
    </style>''', unsafe_allow_html=True)
    st.html('<div class="brand"><div class="brand-title"><span class="brand-icon">诉</span>知诉 · 客服工作台</div><div class="brand-note">本地演示 <span class="pill">AI 辅助 · 人工审核 · 模拟发送</span></div></div>')
