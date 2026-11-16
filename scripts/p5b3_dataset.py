"""Authored synthetic conversations. Run only to create the new immutable manifest."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.domain.contracts import digest
from src.evaluation.p5b_pilot import write_new,now

def cases():
    rows=[]
    def add(split,family,subject,*bodies,facts=None):
        rows.append(dict(case_id=f'B3-{split.upper()}-{1+sum(r["split"]==split for r in rows):02}',split=split,family=family,subject=subject,
            turns=[dict(subject=subject,body=b) for b in bodies],scoped_facts=facts or [],identity='INTERNAL_HELDOUT' if split!='dev' else 'SYNTHETIC_DEV',
            naturalness_review=dict(reviewer='Codex_internal',A1=2,A2=2,A3=2,A4=2,A5=2,A6=2 if len(bodies)>1 else 'N/A',human_review='PENDING')))
    add('dev','camera_connectivity','C200接电脑','青禾数码的 C200 可以直接接笔记本开视频会吗？我看见两种接口，但没找到这个用途的说明。家里是 Windows，不想买完才发现还得加东西。')
    add('dev','camera_connectivity','不要让我等转接','先不用转人工，我坐地铁呢。C200 的 USB 和网口到底哪个能开电脑会议？型号就是 C200，别再问一次了。')
    add('dev','camera_connectivity','Before I order the camera','Can the C200 feed video straight into my laptop for calls? The listing only says USB and Ethernet. I do not want to guess which cable to buy.')
    add('dev','wet_electrical_parcel','门口的箱子湿了','禾木灯具 HM-310 的箱子放在门口淋湿了，底下一大块水渍。我没拆，照片已经附上。今天还要出门，能不能先告诉我怎么放着比较合适？', '我没有拆箱也没有通电。刚找到订单 HM-310，上封写的不是型号，是订单号。别让我搬来搬去了，想先了解能否退回。')
    add('dev','wet_electrical_parcel','雨水进了外箱','快递送来的插电小夜灯纸箱软掉了，订单 HM-312。灯还在箱里，拍的外箱照片在附件，别让我为了拍里面再拆一遍。接下来怎么处理？')
    add('dev','wet_electrical_parcel','A soaked parcel','My desk light arrived in a wet carton, order HM-313. I left it unopened and attached the photo I already took. Please help with the next step; I cannot do a lot of checks at home.')
    add('dev','explicit_human_request','这回请找真人','不要再给我自动回复了，麻烦转人工客服。前面填过的信息就别让我重填，我现在也没空重新讲一遍。')
    add('dev','explicit_human_request','A person please','Please let me speak with a human agent. I have already explained this twice and do not want another questionnaire before you pass my request on.')
    add('dev','urgent_gift_damage','明晚要带去送人','青禾陶瓷的杯子碎了一只，订单 QH-619，照片附了。明晚要去朋友家做客，原本买来送她的。有没有赶得上的处理办法？别先让我把整盒寄出去。')
    add('dev','urgent_gift_damage','盒子和花瓶都裂了','刚打开 QH-620，花瓶一道裂纹，礼盒也压扁了。明天中午要送老师，现在很尴尬。照片已经传了，先帮我确认有什么选择吧。')
    add('validation','billing_documents','会员费是不是扣了两次','昨天在禾页书店续了月会员，支付里出现两笔29元，订单 HY-801。我只点了一次，也没买别的。麻烦核对一下，别让我再付一次试试。')
    add('validation','billing_documents','Two membership charges','I renewed my fictional Pine Reading membership once, but my payment history shows two charges of £4. Reference PR-802. Could you check whether one is just pending before telling me to request a refund?')
    add('validation','billing_documents','收据和发票一起看','禾页 HY-803 的会员费收据重复了一条，另外昨天买的书还没开到发票上。这两件麻烦一起核对，我不想来回写两封。附件是当时的收据，不是新订单。')
    add('validation','billing_documents','发票抬头写错','禾页书店那张发票把公司名字少写了一个字，号码 HY-804。我不需要退书，只想改抬头。应该补什么给你们？')
    add('validation','billing_documents','一本书没上发票','HY-805有三本书，发票只列了两本，收到的书是齐的。麻烦查一下是不是漏开，不用安排补发书。')
    add('validation','garment_size_mismatch','标签和尺码对不上','秋禾衣坊 QY-901 订的是 M，袋子贴 M，衣服领标却是 S。没穿过，想先知道换尺码怎么走，标签照片已经附了。')
    add('validation','garment_size_mismatch','尺码选错了吗','刚收到秋禾的外套，订单 QY-902。页面推荐我买L，穿上肩膀却很紧，不知道是版型还是发错了。还留着吊牌，想问能否换大一点。')
    add('validation','installation_reschedule','师傅又没来','禾居安装 HJ-201 约了今天上午，我请假等到中午都没人联系。希望下次先确认人能来，再让我腾时间。', '刚才我看错了，短信约的是明天下午，不是今天上午。明天我能在家，但三点后要接孩子，只能三点前。请按这个重新核对。')
    add('validation','installation_reschedule','Change my installation slot','I can no longer be home for the Pine Home installation on Friday, booking PH-202. Could the team check Monday morning instead? Please do not confirm a new slot until I agree.')
    add('validation','installation_reschedule','不是再约一次就行','禾居 HJ-203 的安装已经取消两次，真的很烦。下周二全天都在家，别的日子不行。希望你们先核实能不能来，再让我点确认。')
    add('test','old_item_collection','旧椅子一直没取','禾简家具 HJ-401 的新椅子收到了，说好带走的旧椅子还在门口。我不方便自己搬下楼。麻烦看看取旧这件事怎么办。', '补充一下，旧椅子现在已经放回屋里了，不在门口。只有周六上午能开门，别直接安排其他时间来取。')
    add('test','old_item_collection','Nobody collected the old mattress','Pine Rooms delivered my new mattress, order PR-402, but the collection crew never came for the old one. I cannot move it downstairs myself. Please check the collection rather than telling me to book another paid delivery.')
    add('test','old_item_collection','取旧加收的钱','禾简 HJ-403 的旧柜子没人取，原先说一起带走，今天电话里又说可能加钱。能把是否取、费用两件事确认清楚吗？我暂时没答应付。')
    add('test','delivery_address_change','地址少写了楼栋','在纸岸文具下单后才发现地址漏了楼栋，订单 ZA-501。页面显示还在备货，能改吗？不行也请先告诉我，别直接取消。')
    add('test','delivery_address_change','Parcel may be heading to my old place','I put my old address on Paper Shore order PS-502 by mistake. Tracking says dispatched. Is there a way to ask for an address correction? I know it may already be too late.')
    add('test','electrical_safety','插座边上冒了火花','禾电的烧水壶刚烧到一半，插座边突然冒火花，还闻到焦味。我已经关了总开关，没有再碰它。订单 HD-601。现在该怎么处理？', '不是壶身冒烟，是墙插附近有焦味。家里电工说今天先不要恢复那一路电，我也不会再试。壶的售后我想先问退货，不考虑修好继续用。')
    add('test','electrical_safety','The lead sparked','My Pine Heat kettle lead sparked while heating. I switched the power off and have not used it again. Order PH-602. Can you tell me the safe next step without asking me to plug it back in?')
    add('test','electrical_safety','烧水时焦味很重','禾电 HD-603 开始烧水就有很浓的焦味，接线口还有烟，我拔掉了，现在没有继续冒烟。人没受伤。我不敢再用，怎么走售后？')
    add('test','unwanted_marketing','别再发促销了','上回在叶舟小店买过东西以后每天都有促销邮件，我只想停掉广告，订单通知还是要的。邮件底下那个退订链接点了没反应，能帮忙处理吗？')
    add('test','unwanted_marketing','Keep the order emails','I keep receiving Pine Desk promotions after trying the unsubscribe link. Please stop the marketing, but keep delivery updates for my current order PD-701. I do not want the whole account closed.')
    facts=[dict(body='虚构商家栖页书屋的云杉路演示店：周六营业时间10:00–18:00；周日休息。本条只支持营业时间问答，不承诺库存或服务预约。',source='B3 synthetic merchant fixture HOURS-1',authority='INTERNAL_SIMULATED_KNOWLEDGE',merchant_approval=False)]
    add('test','store_hours','周六几点关门','想周六下班后去栖页书屋云杉路店，六点半才到，还开门吗？不买东西，就是去看看。',facts=facts)
    add('test','store_hours','Sunday opening','Is the fictional Spruce Road branch of Qiye Books open on Sunday? I am only checking the hours, not asking for a reservation.',facts=facts)
    assert len(rows)==32
    return rows

if __name__=='__main__':
    rows=cases(); families={}
    for r in rows:
        families.setdefault(r['family'],set()).add(r['split'])
        r['turn_hashes']=[digest(t) for t in r['turns']]
        r['case_hash']=digest(r)
    assert all(len(s)==1 for s in families.values())
    write_new(ROOT/'docs/p5b3/dataset-manifest.json',dict(created_at=now(),source='Codex original synthetic; all authored in same process',identity='INTERNAL_HELDOUT_NOT_INDEPENDENT_GOLD',families={k:list(v)[0] for k,v in families.items()},cases=rows,manifest_hash=digest(rows)))
    print('Frozen 32 conversations /',len(families),'families; DEV 10, validation 10, test 12')
