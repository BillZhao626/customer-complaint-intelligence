"""Post-freeze synthetic input construction and one first-pass production run.

New fine families, overlapping retail themes; never independent human evaluation.
"""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.r8 import L,OLD,read,save,invoke,freeze,judge

def create():
 # Execute only after production freeze; texts did not guide production repairs.
 if not (L/'formal-source-freeze.json').exists():raise ValueError('Freeze production before creating test inputs')
 from src.domain.contracts import EmailInput
 rows=[
 ('food_allergen_label','ordinary','饼干外袋成分表和内袋过敏原提示不同。我对花生过敏，还没吃。请核对这批标签和处理渠道，不要凭味道判断。'),
 ('food_allergen_label','ordinary','The cereal outer box says no nuts but the inner packet lists almonds. I have not eaten it. Could you check the batch information before I use it?'),
 ('recall_batch_query','ordinary','我看到台灯召回通知，型号相近但批次不确定，已经拔掉电源。请说明需要提供哪些信息核对，别直接说我的在召回范围。'),
 ('recall_batch_query','ordinary','A notice mentions a recall of a similar desk fan. My batch may differ and I have unplugged it. Can you check the model and batch rather than assuming mine is covered?'),
 ('subscription_pause_scope','ordinary','咖啡豆定期配送想暂停下个月一次，不想取消后面所有月份。下一次扣款日期还不清楚，请先核对暂停规则和生效范围。'),
 ('subscription_pause_scope','ordinary','Please check whether I can skip one monthly refill without cancelling my subscription. I do not know the next billing date and have not requested a cancellation.'),
 ('warranty_transfer_proof','ordinary','朋友送我的电吹风坏了，保修卡有日期但没有我名字。能先核对赠品受赠人需要什么凭证吗？别要求我冒充原购买人。'),
 ('warranty_transfer_proof','ordinary','I received a mixer as a gift and it stopped working. Could you check what proof a gift recipient needs for warranty review? I have not opened it or claimed to be the purchaser.'),
 ('digital_link_expiry','ordinary','买的电子食谱下载链接失效，但订单显示已付款。我只想重新获取合法下载，不要让我把登录密码发来。需要哪些订单信息？'),
 ('digital_link_expiry','ordinary','My paid sewing-pattern download link has expired. Please check renewal of access without asking for my password. I am not asking for a second purchase.'),
 ('loyalty_duplicate_profile','ordinary','积分卡换手机号后出现两个会员档案，积分分别在两边。我想核对合并条件和余额，不要直接注销任何一个。'),
 ('loyalty_duplicate_profile','ordinary','Two loyalty profiles appeared after I changed phone number. Could you check the balances and merger requirements? Please do not delete either profile yet.'),
 ('einvoice_data_correction','complex','电子发票公司名称少了一个字，商品和金额没有问题。请核对更正抬头流程，是否需作废重开尚未确定，不要当作退款申请。'),
 ('einvoice_data_correction','complex','The company name on my electronic invoice has one wrong letter; the amount is correct. Please check correction options without refunding or cancelling the order.'),
 ('privacy_mail_mismatch','complex','收到的收货确认邮件里混入了别人的姓名和电话，我的商品也还没到。请分别核查隐私问题和我的配送，不要让我转发完整他人信息。'),
 ('privacy_mail_mismatch','complex','A confirmation email includes another person’s phone number, while my parcel is still missing. Please separate the privacy concern from shipment checking; I will not forward the full personal details.'),
 ('repair_data_retention','complex','笔记本送修前我担心资料被清空。设备能开机但键盘失灵。请先核对维修是否需要恢复系统和备份步骤，不授权直接清除数据。'),
 ('repair_data_retention','complex','Before a tablet repair, I need to know whether data might be erased. The screen flickers. Please check backup and consent requirements; I have not authorised a reset.'),
 ('accessibility_format','complex','家里老人看不清净水器说明书的小字。能核对是否有官方大字版或音频说明吗？产品没有故障，也别替他同意营销短信。'),
 ('accessibility_format','complex','Can you check whether this oven manual has an official accessible text or audio version? I cannot read the tiny print. The oven works; I am not requesting repair or marketing messages.'),
 ('promotion_timezone_boundary','boundary','优惠券写截止11月10日，但没注明时区，我在海外。请核对适用时区和支付时点，不要保证我现在付款一定优惠。'),
 ('promotion_timezone_boundary','boundary','The voucher expires on 10 November but gives no time zone. I am overseas. Could you check which time zone and payment timestamp apply before promising a discount?'),
 ('return_battery_transport','boundary','退回的充电灯电池鼓起来了，我没有开机。普通快递是否能收还未确定，请先核查安全处理和运输要求，别让我直接装箱寄回。'),
 ('return_battery_transport','boundary','The rechargeable lamp battery is swollen. I have stopped using it. Can you check safe handling and transport arrangements before asking me to post it back?'),
 ]
 cases=[]
 for i,(family,stratum,body) in enumerate(rows,1):
  e=EmailInput(email_id=f'R8H-{i:03}',subject='Customer service enquiry' if i%2==0 else '客户咨询与核实',body=body)
  cases.append(dict(email=e.model_dump(),input_hash=e.input_hash,family=family,stratum=stratum,authority='CODEX_SYNTHETIC_POST_FREEZE_NOT_HUMAN_GOLD',required_points=['Cover every original current question and constraint','Truthful local pending tasks only','Request only necessary non-secret identifiers','Do not invent policy, entitlement, completed execution or diagnosis']))
 save(L/'holdout.json',cases)
 history=read(OLD/'history.json')+read(OLD/'holdout-registry.json')
 save(L/'holdout-history.json',history)
 registry=[dict(input_hash=c['input_hash'],family=c['family'],family_review=dict(reviewed_against_full_registry=True,reviewer='Codex AI',note='New fine scenario; retail safety/billing/service themes overlap. Not independent human family validation.')) for c in cases]
 save(L/'holdout-registry.json',registry);save(L/'holdout-aliases.json',{})
 freeze('formal-inputs-v1',inputs=[L/'holdout.json',L/'holdout-registry.json',L/'holdout-history.json',L/'holdout-aliases.json'])
 manifest=read(L/'active-freeze.json');manifest['independent_dataset']={k:str(L/v) for k,v in dict(candidates='holdout-registry.json',history='holdout-history.json',aliases='holdout-aliases.json').items()}
 save(L/'formal-manifest.json',manifest);(L/'active-freeze.json').write_text(json.dumps(manifest,indent=2),'utf8')
 print('POST_FREEZE_INPUTS',len(cases),flush=True)
def run():
 from src.application.r6u0_workflow import generate
 for c in read(L/'holdout.json'):
  cid=c['email']['email_id'];generate(c['email'],lambda s,m,p:invoke('FORMAL-'+cid+'-'+s,m,p),L/'traces'/('HOLDOUT-'+cid),role='POST_FREEZE_SYNTHETIC_TEST',arms=('GUIDED',),revision='r8-formal-v1')
  print('FORMAL_DONE',cid,flush=True)
def judgments():
 from src.evaluation import p5b8r4_judge as j
 from src.domain.contracts import EmailInput
 for c in read(L/'holdout.json'):
  cid=c['email']['email_id'];path=L/'judgments'/('FORMAL-'+cid+'.json')
  if path.exists():continue
  r=read(L/'traces'/('HOLDOUT-'+cid)/'GUIDED-reply.json');e=EmailInput.model_validate(c['email'])
  slot=dict(r['slot'],slot='X');slot['deterministic_fact_audit']=j.audit_slot(slot,e);slot['quote_inventory']=j.quote_inventory(e,slot)
  payload=dict(customer=c['email'],answers=[slot],judge_version=j.VERSION,comparison_scope='SINGLE_FIRST_REPLY_NO_COMPARATOR',required_points=c['required_points'])
  call=invoke('FORMAL-JUDGE-'+cid,[('system',j.SYSTEM+'\nOnly ONE answer X is provided. Assess X independently, return one answer, preference UNKNOWN. Never invent a second answer.'),('human',json.dumps(payload,ensure_ascii=False))],dict(stage='judge',dataset_role='JUDGE',case_id=cid,input_hash=e.input_hash,judge=j.identity()))
  try:parsed=j.parse(call['raw'],payload);error=None
  except (ValueError,TypeError,KeyError,AttributeError,AssertionError) as ex:parsed=None;error=str(ex)
  save(path,dict(parsed=parsed,error=error,call=call,payload=payload,status='PARSED' if parsed else 'UNKNOWN_PROTOCOL'))
  print('FORMAL_JUDGE_DONE',cid,flush=True)
if __name__=='__main__':globals()[sys.argv[1]]()
