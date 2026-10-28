"""Light inbox styles, scoped to stable app keys and Streamlit test IDs."""
import streamlit as st


def apply():
    st.markdown('''<style>
    :root {--ink:#25283b;--muted:#5b6274;--line:#e9eaf0;--accent:#6554c7;}
    .stApp {background:#f8f9fc;color:var(--ink);}
    [data-testid="stHeader"] {height:0;background:transparent;}
    [data-testid="stToolbar"] {display:none;}
    .block-container {max-width:none;padding:1.1rem 1.5rem 1rem;}
    h1 {font-size:1.35rem!important;} h3 {font-size:1.08rem!important;padding:.2rem 0 .45rem!important;}
    [data-testid="stVerticalBlock"] {gap:.65rem;}
    [data-testid="stText"] {white-space:pre-wrap;overflow-wrap:anywhere;font-family:inherit;font-size:15px;line-height:1.65;}
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {color:var(--muted);font-size:13px;line-height:1.5;}
    [data-testid="stCaptionContainer"] {opacity:1!important;}
    [data-testid="stTextArea"] textarea {font-size:16px;line-height:1.6;background:#fff;color:var(--ink);}
    .brand {display:flex;align-items:center;justify-content:space-between;padding:0 0 .65rem;}
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
    .st-key-inbox_pane {padding:6px 16px 0 0;border-right:1px solid var(--line);}
    .st-key-inbox_pane [data-baseweb="select"] > div {padding-left:9px;padding-right:5px;font-size:13px;}
    .st-key-copilot_pane {padding:8px 0 0 18px;border-left:1px solid var(--line);}
    .st-key-inbox_scroll {height:calc(100dvh - 375px)!important;min-height:220px;border:0!important;}
    .st-key-conversation {height:280px!important;min-height:180px;border:0!important;background:transparent;}
    .st-key-conversation_single {max-height:260px;overflow-y:auto;}
    .st-key-assistant_scroll {height:calc(100dvh - 240px)!important;min-height:270px;border:0!important;}
    .st-key-inbox_scroll [data-testid="stButton"] button {width:100%;text-align:left;justify-content:flex-start;border:0;padding:15px 12px;background:transparent;}
    .st-key-inbox_scroll [data-testid="stButton"] button p {text-align:left;font-size:13px;line-height:1.6;margin-bottom:5px;}
    .st-key-inbox_scroll [data-testid="stButton"] button strong {font-size:15px;font-weight:600;}
    .st-key-inbox_scroll .st-key-selected_case button {background:#eeebfb;border:1px solid #dcd6f5;box-shadow:0 2px 8px #42378208;}
    .st-key-inbox_scroll [data-testid="stButton"] button:hover {background:#f6f5fc;}
    .conversation-title {font-size:20px;font-weight:650;margin:3px 0 4px;}
    .message {max-width:100%;border-radius:13px;background:#fff;border:1px solid #e9eaf0;padding:18px 20px;margin:8px 0 14px;font-size:16px;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere;}
    .message.outgoing {margin-left:auto;background:#eeecfc;}
    .message-meta {font-size:13px;color:#53586b;margin-bottom:7px;white-space:normal;}
    .next-step {font-size:14px;color:#504776;background:#efedf8;border-radius:8px;padding:10px 12px;line-height:1.5;}
    .st-key-composer {background:#fff;border:1px solid #dfdce9;border-radius:14px;padding:16px 18px;box-shadow:0 6px 24px #30245b06;}
    .composer-heading {font-size:15px;font-weight:600;}
    .st-key-composer [data-testid="stTextArea"] label {display:none;}
    .st-key-composer textarea {border:0!important;}
    .st-key-suggestion_card {border-radius:13px;background:linear-gradient(125deg,#f0edff,#f8f0f7);padding:15px;}
    .st-key-suggestion_card [data-testid="stText"] {font-size:15px;line-height:1.65;}
    .section-label {font-size:13px;color:#56516b;margin:4px 0 7px;}
    .need {font-size:15px;font-weight:600;line-height:1.6;margin:4px 0 7px;}
    .st-key-region_switch {display:none;}
    .inbox-heading {font-size:17px;font-weight:650;display:flex;align-items:center;gap:8px;margin-bottom:2px;}
    .inbox-dot,.demo-dot {display:inline-block;width:7px;height:7px;border-radius:50%;background:#7e73c6;}
    .demo-dot {background:#538071;margin-right:5px;}
    .draft-label {float:right;color:#676078;font-size:12px;font-weight:450;padding-top:3px;}
    .copilot-orb {display:inline-flex;border-radius:9px;background:#ebe7fb;color:#6350b7;width:30px;height:30px;align-items:center;justify-content:center;margin-right:9px;}
    .copilot-title {display:inline;font-size:17px;font-weight:650;}
    .route-card {border:1px solid #e6e2f2;background:#f1eff9;border-radius:10px;padding:12px 14px;font-size:13px;line-height:1.7;}
    .st-key-copilot_pane [data-testid="stMarkdownContainer"] p {font-size:14px;line-height:1.75;}
    .st-key-inbox_pane [data-testid="stExpander"] {background:#fff;}
    .st-key-assistant_scroll {background:transparent;}
    .st-key-inbox_scroll [data-testid="stVerticalBlock"] {gap:.15rem;}
    .block-container > [data-testid="stVerticalBlock"] > [data-testid="stTabs"] > div > [data-baseweb="tab-list"] {margin-bottom:8px;}
    .block-container > [data-testid="stVerticalBlock"] > [data-testid="stTabs"] > div > [data-baseweb="tab-list"] button:last-of-type {margin-left:auto;color:#687084;font-size:13px;}
    @media (min-width:1101px) {.st-key-layout_conversation > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {gap:1.5rem;}}
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
    st.html('<div class="brand"><div class="brand-title"><span class="brand-icon">诉</span>知诉 <span style="font-size:14px;font-weight:450;color:#5b6274"> / 客服收件箱</span></div><div class="brand-note"><span class="demo-dot"></span> 本地演示 <span class="pill">AI Copilot</span></div></div>')
