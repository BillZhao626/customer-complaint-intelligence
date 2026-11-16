"""Source-triggered service checks and bounded advice, with no merchant assumptions."""
import re


# These profiles recognize common wording. They supplement Issue extraction and
# leave unmatched requests to the existing planner, rather than classifying them.
PROFILES = {
    'cancellation_payment_obligations': (
        r'订金|定金|预付款|尾款|deposit|balance|prepayment',
        'aftersales_request', '核实取消生效条件、订金处理、尾款截止日期及取消期间是否仍需付款 / verify cancellation effectiveness, deposit treatment, balance due date and payment obligations during cancellation review',
        'Locate the actual order and cancellation terms. Check deposit refund/retention, when cancellation takes effect, the balance deadline and whether an approved suspension or extension applies. A pending enquiry does not suspend payment. If a deadline may be near, ask the customer to contact official human support promptly to confirm the current payment notice. Do not assume they must stop paying, continue paying, or receive a full refund.'),
    'affected_second_product': (
        r'白鞋|鞋子|shoes?|footwear',
        'aftersales_request', '分别核查掉色商品与受染商品，按受染商品实际购买渠道核实评估受理 / verify both colour-transfer items and route assessment through the affected item purchase channel',
        'Pause unverified cleaning and preserve both items. Explain a conditional assessment route for the separately affected item: if purchased here, ask this seller aftersales to verify acceptance; if purchased elsewhere, contact that seller or brand official aftersales to verify the assessment route. Ask for the missing purchase channel, avoid assuming acceptance or responsibility, and keep the original item defect investigation.'),
    'electrical_load_boundary': (
        r'插线板|插排|延长线|extension (?:lead|cord)|power strip|cable reel',
        'human_input_request', '核实总负载与电气额定值，不把换插座或轮流使用当作已核实的安全方案 / verify combined load and electrical ratings without certifying another socket or alternating use as safe',
        'Add the stated appliance loads and compare only with the supplied rating. Do not advise testing an overload. A different socket does not establish an independent circuit or suitable capacity. Do not certify separate sockets, another circuit, or one-at-a-time use as a safe workaround from wattage alone. Hold the proposed combination and obtain the exact equipment instructions and qualified electrical verification; do not recommend a heater on an extension lead.'),
    'earliest_consumable_limit': (
        r'滤芯|filter|cartridge|consumable',
        'human_input_request', '分别跟踪日历与用量，以先到者为准；用量未知时不能用最长日历期限代替 / track time and usage independently and apply whichever comes first; unknown usage does not authorize the longest calendar interval',
        'When the supplied rule says whichever comes first, keep both limits. A usage estimate is not a measurement or prediction of future consumption. If usage cannot be established, do not advise waiting for the calendar maximum as a fallback. Identify the official usage/replacement check before relying on continued service. Do not promise filtration or water safety.'),
    'partial_bundle_resolution': (
        r'组合装|组合价|组合商品|组合套装|两件.{0,8}折|bundle|multi.pack|set of',
        'aftersales_request', '核实组合商品单件换货或部分退货授权、保留其余商品与优惠分摊；按实际付款分配核对退款或贷记调整和适用费用 / verify partial bundle replacement/return, preserve retained items, paid-price discount allocation, refund/credit adjustment and applicable fees',
        'For a defective component, verify separate replacement versus partial return while retaining the other components and avoiding automatic whole-set cancellation. For a return, explicitly check the actual paid-price allocation, any retained-item discount recalculation and resulting refund/credit/bill adjustment, without quoting an unverified amount. For replacement, verify charges and conditions. Do not mechanically demand an unpaid-service fee-removal branch for goods already purchased.'),
    'accessible_manual': (
        r'屏幕阅读器|screen.reader|image.only (?:PDF|manual)|PDF全是图片',
        'human_input_request', '核实准确型号及可读说明书，清洗前安全步骤须向官方产品支持取得可读版本；内容未确认前不开始清洗 / verify exact model and accessible manual; obtain readable pre-cleaning safety instructions from official product support before cleaning',
        'Use the supplied catalogue only within its model and content scope. Request the missing model first; do not request an image-only PDF the customer cannot read. If cleaning safety is specifically requested and absent from the record, identify the official product-support check for readable cleaning warnings/instructions and advise postponing unverified cleaning until received. Never invent the missing cleaning procedure.'),
    'multi_parcel_return': (
        r'两箱|多箱|各装一箱|各.{0,8}装.{0,3}箱|两个包裹|分.{0,8}箱|two (?:boxes|parcels)|separate (?:boxes|parcels)|split.{0,20}(?:box|parcel)|each.{0,20}(?:own|separate).{0,10}(?:box|parcel)',
        'aftersales_request', '核实退回可否拆装、多箱包装及每箱独立有效运单授权；已有一张运单不等于两箱均获授权 / verify safe disassembly, permitted packing and a distinct valid waybill/authorization for EACH return parcel',
        'Before handing over either parcel, ask aftersales/carrier whether splitting is accepted, whether the existing waybill covers one or multiple pieces, and how an additional valid label/authorization is obtained for the second parcel. Never duplicate one single-parcel label or assume ordinary packaging rules authorize splitting. Preserve the existing waybill; hold packing/handover until approved instructions are known.'),
    'locker_expiry': (
        r'快递柜|柜机|locker',
        'logistics_followup', '到已说明截止前立即核实取件码重发、延期、费用和无法及时确认时的获准替代方式；不得标记取走 / promptly verify code reissue, extension, charges and approved alternatives before the stated collection expiry, without marking collected',
        'Contact the operator via its official cabinet/order contact promptly before the stated expiry. Ask reissue/extension, fees and an approved staffed or other collection arrangement if the code cannot be restored in time. If not reachable, retain timestamp/report reference and seek explicit instructions; do not guarantee an extension, advise waiting past expiry or mark collected. Do not request the secret code.'),
    'optional_service_removal': (
        r'组装|安装服务|assembly|installation service|add.on service|optional service',
        'aftersales_request', '核实可选服务授权、独立取消、配送依赖和费用状态；已收款退费或账单调整，未收款核实未来计费 / verify optional service authorization, separability, delivery dependency, charge state and refund or billing adjustment if paid, future charge removal if unpaid',
        'Check whether the service was authorized and can be removed separately while preserving the requested delivery. Explicitly verify whether its fee was charged or collected: if paid, check refund/credit/bill adjustment; if unpaid, check that future billing will be removed. Separately priced alone is not this check. Do not actually cancel, refund or change delivery without consent.'),
    'contact_privacy': (
        r'(?:别人|他人|陌生人|第三方).{0,12}(?:号码|电话)|(?:another person|someone else|stranger|wrong|unfamiliar).{0,24}(?:phone|mobile|contact) number|(?:号码|电话).{0,12}(?:不认识|不是我的|是别人的)',
        'support_followup', '核查隐私问题及订单授权收件联系方式 / verify privacy concern and authorized recipient contact',
        'Apologize and check the authorized order contact. Do not ask for, repeat, or forward a third party’s full number. Use a non-sensitive order reference or message date only if needed.'),
    'missing_shipment': (
        r'(?:包裹|快递|货物|parcel|package|shipment|delivery).{0,25}(?:没收到|没有收到|未收到|不见|丢|没到|missing|never arrived|not arrived|not received)|(?:没收到|未收到|没有收到).{0,12}(?:包裹|快递|货物)|(?:haven.t received|didn.t get).{0,22}(?:parcel|package|shipment)',
        'logistics_followup', '核查物流轨迹及未收件情况 / verify missing shipment with logistics',
        'Check the tracking and delivery status using existing references first. If the parcel cannot be located, check replacement or another remedy under applicable policy. No confirmed loss, delivery, or replacement.'),
    'promotion_deadline': (
        r'优惠券|优惠码|促销券|折扣码|促销|优惠活动|voucher|coupon|promo(?:tion)?(?: code)?',
        'billing_request', '核实商家优惠截止时区及适用付款时间戳 / verify promotion expiry zone and eligible payment timestamp',
        'Check this merchant’s promotion terms and which payment timestamp counts. If unknown, ask billing to verify using the promotion reference and, only if paid, the payment timestamp. Do not recommend a supposedly safe local time or substitute another platform’s rule.'),
    'subscription_skip': (
        r'订阅|定期配送|暂停规则|单次跳过|subscription|recurring delivery|monthly refill',
        'billing_request', '核实单次跳过、下次扣款日及后续订阅权益 / verify one-cycle skip, next billing date and plan continuity',
        'If the subscription channel offers a one-cycle skip, check its effective cycle and billing date, whether that cycle is charged, and how the next refill/bill date and discount are affected. If unavailable, verify alternatives with support. Mention stopping renewal and resubscribing only as an option to check first for effects on price, discounts, timing and benefits. Preserve the current subscription and do not suggest cancellation as the default.'),
    'delegate_pickup': (
        r'代取|代领|(?:collect|pick up).{0,20}(?:instead|on my behalf)|(?:someone else|sister|brother|friend|partner|proxy).{0,22}(?:collect|pick up)',
        'store_service_request', '核实代取授权、最少凭证及保留时间 / verify delegate collection, minimum proof and hold period',
        'Use the collection store and reservation reference if available. Verify whether delegation is permitted, minimum proof and hold period. Ask only for missing essentials. Do not imply collection is authorized, locked or released, or solicit full ID images or an unneeded full name.'),
    'visit_reschedule': (
        r'预约|上门|appointment|visit|booked slot',
        'store_service_request', '核查预约改期与可用时段 / verify rescheduling and available visit times',
        'Use the stated date and requested window. If the booking reference is missing, ask for it first. Preserve the current slot until a new one is confirmed. Keep any access-code restriction as an intake condition, and do not request the code by email.'),
    'service_loan': (
        r'借用|备用机|代用机|周转机|loaner|borrow|temporary replacement',
        'store_service_request', '核实维修期间借用设备库存、适配与取还条件 / verify repair loan availability, compatibility and terms',
        'Check the servicing location, repair reference if needed, compatible model, availability and pickup/return terms. Preserve any stated date. Inquiry only; no booking, rental charge or reservation claim.'),
    'uncomfortable_odor': (
        r'异味|刺鼻|气味很重|strong (?:smell|odou?r)|unpleasant (?:smell|odou?r)|pungent|chemical smell',
        'aftersales_request', '核实材质、护理及退换退款适用条件 / check material, care and return, exchange or refund options',
        'Acknowledge discomfort and support pausing use. Verify the actual material and care label and offer to check applicable return, exchange or refund options. Ventilation or a change in smell does not establish safety. Do not diagnose, direct continued use, or promise eligibility.'),
    'sync_file_recovery': (
        r'云同步|云端|同步(?:盘|文件|目录|副本)|cloud sync|cloud cop(?:y|ies)|sync(?:ed|hronized)? (?:cop(?:y|ies)|folders?|files?)|\b(?:iCloud|OneDrive)\b',
        None, 'Verify the exact app, version and platform, deletion propagation, retained versions and recoverability.',
        'Preserve the original while the behavior is unknown. Check the official guidance for the actual configuration. If copying, make an independent copy and verify it can be opened or restored. Do not suggest moving, deleting or clearing the only original before those checks.'),
    'gift_card_intake': (
        r'礼品卡|储值卡|gift[ -]card',
        None, 'Verify card activation and transactions using the receipt or other non-sensitive purchase reference first.',
        'Use the issuer’s official support. If more evidence is needed, verify the secure route and minimum accepted identifier. Do not request the full card number, redeemable code, PIN or card-back image in ordinary email.'),
    'tariff_reconciliation': (
        r'电价|费率|tariff|unit price',
        None, 'Verify the effective tariff date, billing interval, recorded readings and authorized allocation method.',
        'Use the actual statement and billing record. Ask the official billing team to check any missing boundary reading or applicable estimate method. Do not promise a split, recalculation or which tariff will apply to all units before verification.'),
    'wallpaper_match': (
        r'墙纸|壁纸|wallpaper',
        None, 'Verify match type, starting motif, repeat, drop length and trimming allowances for the exact product.',
        'Distinguish illustrative matching spacing from the physical cut length. Include the assumptions in any estimate and verify the actual trim, starting motif and offcut rules before claiming an order quantity.'),
}
QUALIFIERS = {
    'cancellation_payment_obligations': r'取消|撤销|cancel|withdraw',
    'affected_second_product': r'染|掉色|colour transfer|color transfer|stain|dyed|dye transfer|colour.{0,12}(?:rub|transfer)|color.{0,12}(?:rub|transfer)',
    'electrical_load_boundary': r'功率|负载|额定|同时|一起|[wW]\b|load|rating|rated|watt|together',
    'earliest_consumable_limit': r'先到|先达到|whichever.{0,12}first|earlier of',
    'partial_bundle_resolution': r'只退|部分退|单独换|单独.{0,5}处理|其他.{0,8}留|只.{0,8}(?:换|退)|partial return|return.{0,15}(?:part|only)|only.{0,30}(?:unopened|return)|keep.{0,20}(?:other|rest|two)',
    'multi_parcel_return': r'退回|寄回|退货|return|send.{0,10}back',
    'locker_expiry': r'到期|截止|expire|expir|deadline',
    'optional_service_removal': r'取消|移除|没选|未选|不需要|没有选|remove|cancel|didn.t (?:choose|select)|don.t (?:want|believe)|not (?:choose|select|want)',
    'promotion_deadline': r'截止|到期|时区|付款时间|expir|deadline|time zone|timezone|payment timestamp',
    'subscription_skip': r'跳过|暂停|skip|pause|miss.{0,8}(?:cycle|delivery)',
    'service_loan': r'维修|检修|repair|being serviced',
    'visit_reschedule': r'改期|改到|换到|调整.{0,8}时段|reschedul|slot can be moved|move (?:my|the|our) (?:slot|visit|appointment)',
    'sync_file_recovery': r'删除|删文件|清(?:理)?空间|移出|移走|delet|remov|clear (?:device )?space|mov(?:e|ing)\s+(?:a |the |my )?(?:files?|original|cop)',
    'gift_card_intake': r'激活|使用|消费|余额|核查|activation|used|redeem|balance|transaction',
    'tariff_reconciliation': r'抄表|分段读数|计费区间|meter.{0,18}(?:reading|interval)|reading (?:dates?|periods?|intervals?)',
    'wallpaper_match': r'对花|花距|图案重复|pattern repeat|match(?:ed|ing) (?:cut|drop)',
}
RESOLVED = {
    'missing_shipment': r'(?:包裹|快递).{0,10}(?:已经收到|找到了)|parcel (?:has arrived|was found)',
    'uncomfortable_odor': r'(?:异味|气味).{0,8}(?:已经消失|已消除)|(?:smell|odou?r) (?:has gone|went away)',
    'subscription_skip': r'(?:已经|已)(?:成功)?(?:跳过|暂停)|(?:already|successfully) (?:skipped|paused)',
    'service_loan': r'不(?:再)?需要.{0,8}(?:备用机|借用)|(?:no longer need|don.t need|do not need).{0,16}(?:loaner|temporary replacement)',
}


def source_topics(email):
    source = email.subject + '\n' + email.body
    clauses = [part.strip() for part in re.split(r'[。！？!?\n]+', source) if part.strip()]
    topics = {}
    for name, (pattern, _, _, _) in PROFILES.items():
        if name in QUALIFIERS and not re.search(QUALIFIERS[name], source, re.I):
            continue
        if name in RESOLVED and re.search(RESOLVED[name], source, re.I):
            continue
        quotes = [part for part in clauses if re.search(pattern, part, re.I)]
        if name == 'optional_service_removal':
            # Physical manufacturing access/cover removal is not cancellation
            # of a purchased assembly service. Explicit service fees still win
            # in a mixed email containing a separate manufacturing question.
            manufacturing = r'\b(?:for|during)\s+(?:(?:manufacturing|factory|production)\s+)?assembly\b|\bassembly (?:instructions|guide|only)\b|manufacturing access|(?:生产|制造|工厂)装配|组装说明|装配说明'
            explicit_service = r'assembly (?:service|fee|charge)|(?:paid|optional) assembly|installation service|(?:组装|安装)(?:服务|费)'
            quotes = [q for q in quotes if not re.search(manufacturing,q,re.I) or re.search(explicit_service,q,re.I)]
        if quotes:
            topics[name] = quotes
    return topics


def strengthen_plan(email, actions):
    topics = {name: quotes for name, quotes in source_topics(email).items() if PROFILES[name][1] is not None}
    for name, quotes in topics.items():
        pattern, kind, goal, _ = PROFILES[name]
        if name == 'delegate_pickup':
            for action in actions:
                delivery = re.search(r'物流|配送|运单|快递|\b(?:shipment|carrier|delivery|tracking|dispatch)\b', action['goal'], re.I)
                authorization = re.search(pattern+r'|(?:授权|延期|保留期限)|\b(?:authori[sz]|extend|extension|hold period)', action['goal'], re.I)
                if action['kind'] == 'logistics_followup' and authorization and not delivery:
                    action['kind'] = kind
                    action['evidence'] = list(dict.fromkeys(action['evidence'] + quotes))
        matching = [
            action for action in actions if action['kind'] == kind
            and re.search(pattern, action['goal'] + ' ' + ' '.join(action['evidence']), re.I)
        ]
        if name == 'earliest_consumable_limit' and not matching:
            # Extraction can retain both limits while leaving out the product
            # noun. Strengthen the one existing dual-limit check in that case.
            checks = [
                action for action in actions if action['kind'] == kind
                and re.search(r'个月|\b(?:months?|weeks?)\b', action['goal'], re.I)
                and re.search(r'\d+\s*(?:升|litres?\b|liters?\b|gallons?\b)', action['goal'], re.I)
            ]
            if len(checks) == 1:
                matching = checks
                checks[0]['evidence'] = list(dict.fromkeys(checks[0]['evidence'] + quotes))
        if name == 'subscription_skip' and len(topics) == 1:
            # Single-cycle eligibility and its billing date share one support
            # check, even if extraction split them into separate issues.
            linked = [
                action for action in actions
                if action['kind'] in ('billing_request','clarification_request','support_followup')
                and re.search(pattern+r'|下一次扣款|下次扣款|next billing date',action['goal'],re.I)
            ]
            if len(linked) > 1:
                primary = linked[0]
                primary.update(kind=kind,goal=goal,
                               issue_ids=list(dict.fromkeys(i for item in linked for i in item['issue_ids'])),
                               evidence=list(dict.fromkeys(q for item in linked for q in item['evidence'])),
                               priority='high' if any(item['priority']=='high' for item in linked) else 'normal')
                actions = [a for a in actions if a is primary or all(a is not item for item in linked)]
                continue
        if not matching and name == 'subscription_skip' and len(topics) == 1 and len(actions) == 1:
            # A single subscription-rule question has a concrete owner even
            # when analysis leaves its process "unclear."
            action = actions[0]
            if action['kind'] in ('clarification_request','support_followup') and re.search(pattern, action['goal'], re.I):
                action['kind'] = kind
                matching = [action]
        if not matching:
            actions.append(dict(kind=kind, goal=goal, issue_ids=[], evidence=quotes, priority='normal'))
        for action in matching:
            if goal not in action['goal']:
                action['goal'] += '；' + goal
    return actions


def verified_facts(email, facts):
    """Only current-input, authorized conclusions are usable as business facts."""
    if facts.get('status') != 'KNOWN':
        return []
    return [
        fact for fact in facts.get('facts', [])
        if fact.get('input_hash') == email.input_hash and fact.get('source_id')
        and fact.get('authority') in ('VERIFIED_CONNECTOR', 'AUTHORIZED_FIXTURE')
        and fact.get('conclusion')
    ]


def service_checks(email, runtime):
    topics = source_topics(email)
    source = email.subject + '\n' + email.body
    identifiers = [
        ref for ref in runtime.get('context', {}).get('identifiers', [])
        if ref and ref in source
    ]
    return dict(
        topics=[dict(topic=name, source_quotes=quotes, required_check=PROFILES[name][2],
                     possible_solutions=PROFILES[name][3]) for name, quotes in topics.items()],
        customer_reported_references=identifiers,
        verified_facts=verified_facts(email, runtime.get('facts', {})),
        intake_rule='Use available authorized records and source references first. Ask only for the smallest missing identifier. An order mentioned by the customer is not a verified order record.',
        catalog_rule='Use an actual verified order to identify the product, then verify specification and stock before naming a specific available replacement. Otherwise explain the needed fit or feature conditionally.',
        path_requirements=dict(
            purpose='Complete the minimum service path for each current customer need. These checks do not authorize or create tasks.',
            change='When changing one component, establish separability, what stays in place, and any price or fee consequence before proposing the change.',
            handover='Before advising a return or handover, verify permitted method, effective acceptance time, evidence of acceptance and any relevant charges. If unavailable, identify the exact official check and safe interim option.',
            scope='For multiple items, packages or people, verify whether each authorization, label or receipt applies to each one.',
            conflict='Treat conflicting pages, currencies or records as evidence to reconcile. Verify the actual transaction basis; do not select one disputed display as authoritative.',
            advice='Apply verified specifications only in their measured direction and conditions. Include other clearances or prerequisites that could change the conclusion.',
            source='Keep customer-reported observations separate from verified catalogue/order facts, including within the same sentence.',
        ),
    )
