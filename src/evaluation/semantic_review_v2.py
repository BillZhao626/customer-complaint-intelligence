"""Versioned AI review preparation of saved v3 outputs under owner policy v2."""
import re
from src.domain.contracts import digest
from src.domain.versioned_analysis import stored_analysis,output_hash
from src.application.research_policy_v2 import POLICY_HASH, assess, language
from src.application.reply_review import inspect_reply
from src.evaluation.semantic_review import validate_review as validate_parent,source_text

VERSION='p38-content-rubric-v2'
MAPPING={
 'issue_coverage':'important_issues','over_splitting':'important_issues','wrong_merging':'important_issues',
 'object_reason_resolution':'important_issues','evidence_support':'evidence_support',
 'risk_urgency':'safety_privacy_multi','customer_importance':'important_issues','handling_order':'important_issues',
 'routing_certainty':'evidence_support','summary_facts':'summary_facts','reply_language':'language_and_tone',
 'reply_coverage':'reply_requests','repeated_information':'repeated_information','mechanical_disclaimer':'language_and_tone',
 'invented_actions':'unauthorized_claims','material_promises':'unauthorized_claims',
 'safety_privacy':'safety_privacy_multi','multi_issue_reply':'safety_privacy_multi'}
GUIDANCE={
 'issue_coverage':'逐一对照所有未解决事件；回电未履行与保修未答应分开。',
 'over_splitting':'同一服务失败的改述不能多算问题，需独立事件和证据。',
 'wrong_merging':'独立未解决事件不能合并；邮件分母仍为一。',
 'object_reason_resolution':'分别审核对象、原因、已解决/未解决，背景不是当前投诉。',
 'evidence_support':'逐字存在不代表语义蕴含；检查每个判断对应的具体引文。',
 'risk_urgency':'按新版一般求助medium、强诉求high、明确不急low；危险事实优先；冷锅柄/火花high、普通碰撞medium。',
 'customer_importance':'一起跟进不能自动equal；不得用业务顺序反推客户主次。',
 'handling_order':'风险与流程建议单独评价，保留发票，不虚构reported_dependency。',
 'routing_certainty':'发票建议客服协调；门店提及/流程分类不证明责任，unclear与unknown保留。',
 'summary_facts':'摘要是否完整、有无编造，需人工逐项审核。',
 'reply_language':'客户主要语言/明确语言要求优先；混合无法确定时保留双语候选。',
 'reply_coverage':'是否回答主要诉求并给出可执行的合理下一步，需要人工判断。',
 'repeated_information':'逐项核对再次索要的信息是否原文已有。',
 'mechanical_disclaimer':'单独评价内部执行边界免责声明是否机械、挤占有用回答。',
 'invented_actions':'转交、批准、处理、记录等已执行动作缺依据属于缺陷。',
 'material_promises':'退款、赔偿、配送、期限承诺单独检查否定范围和转折。',
 'safety_privacy':'安全和隐私遗漏单列关键错误，不能被均分掩盖。',
 'multi_issue_reply':'多问题是否只回答一个；引用完整回复并逐一核对。'}


def build_review(run,parent):
    validate_parent(run,parent)
    value=stored_analysis(run) if run.result else None
    finding=assess(run.email.body)
    checks=dict(source_schema=run.config.schema_version,original_accepted=bool(value),
        evidence_spans='passed' if value else 'unavailable',issue_count=len(value.issues) if value else None,
        email_count=1,policy_candidate=finding,reply_lexical=inspect_reply(value.suggested_reply) if value else None,
        source_main_language_candidate=language(run.email.body),reply_language_candidate=language(value.suggested_reply) if value else None,
        semantic_correctness=None)
    dimensions={}
    for name,old in MAPPING.items():
        item=parent['dimensions'][old]
        note=GUIDANCE[name]
        if value:
            note+=' 该样本P3.7候选意见：'+item['opinion']
            if name=='risk_urgency' and finding['urgency']:
                note+=f" 新版词面候选紧急度={finding['urgency']}；原始v3={value.urgency}，保留原输出与旧七字段参考，不自动改签。"
            if name=='reply_language':note+=f" 词面语言候选：来信{checks['source_main_language_candidate']} / 回复{checks['reply_language_candidate']}；含明确语言要求时需结合语境。"
            if name=='routing_certainty':note+=' 当前问题路由：'+', '.join(f'{i.issue_id}={i.routing_team}/{i.attribution_certainty}' for i in value.issues)
        dimensions[name]=dict(ai_opinion=note if value else '无正式接受预测；不可内容评分，失败保留分母。',
            severity_candidate=item['severity'],evidence=item['evidence'],human_score=None,human_critical_error=None,
            status='pending_human' if value else 'unaccepted_output')
    packet=dict(protocol=VERSION,policy_hash=POLICY_HASH,parent_packet_hash=parent['packet_hash'],run_id=run.run_id,
        sample_id=run.email.email_id,input_hash=run.input_hash,config_hash=digest(run.config.model_dump()),
        source_schema=run.config.schema_version,output_hash=output_hash(run),raw_hashes=[digest(a.raw_output) for a in run.attempts],
        deterministic_checks=checks,dimensions=dimensions,human_status='pending',human_reviewer=None,human_declaration=False,
        official_content_score=None,new_policy_reference=None,reply_status='unreviewed_unsent',ai_opinions_only=True)
    packet['packet_hash']=digest(packet)
    return packet


def validate_review(run,parent,packet):
    if packet!=build_review(run,parent):raise ValueError('Review identity/citations/pending status mismatch')
    return packet
