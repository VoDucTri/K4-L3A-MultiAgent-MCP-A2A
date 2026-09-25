# L3A Architecture Record

Tài liệu này ghi lại kiến trúc thiết kế hệ thống Multi-Agent A2A (Agent-to-Agent) phục vụ xử lý tranh chấp và bồi hoàn thương mại điện tử cho phân ban L3A. Mọi quyết định thiết kế đều hướng tới tính xác minh độc lập, tuân thủ nghiêm ngặt Public JSON Contracts và phân lập quyền hạn truy xuất bằng chứng MCP.

---

## 1. System Overview

Hệ thống hoạt động theo mô hình luồng tác tử cộng tác có giám sát (Orchestrated Multi-Agent Pipeline) kết hợp kiểm định bất biến (Invariants Verification):

```text
               ┌────────────────────────────────────────────────────────┐
               │                  inputs/<case_id>.json                 │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
                               ┌───────────────────────┐
                               │  Coordinator / Router │
                               └───────────┬───────────┘
                                           │ (Task Assignment & Parallel Handoff)
             ┌─────────────────────────────┼─────────────────────────────┐
             ▼                             ▼                             ▼
   ┌───────────────────┐         ┌───────────────────┐         ┌───────────────────┐
   │  Order/Item Agent │         │   Payment Agent   │         │  Shipment Agent   │
   └─────────┬─────────┘         └─────────┬─────────┘         └─────────┬─────────┘
             │                             │                             │
             │ [get_order]                 │ [get_order_payments]        │ [get_shipment_summary]
             │ [get_order_items]           │ [get_payment_timeline]      │
             │ [get_sellers]               │ [get_refund_timeline]       │
             │ [get_product_context]       │                             │
             │                             │                             │
             └─────────────────────────────┼─────────────────────────────┘
                                           │
                                           ▼ (Specialist Evidence Bundles)
                               ┌───────────────────────┐
                               │     Policy Agent      │ ◄── [get_policy]
                               └───────────┬───────────┘     [get_customer_history]
                                           │ (Draft Case Output)
                                           ▼
                               ┌───────────────────────┐
                               │    Verifier Agent     │
                               └───────────┬───────────┘
                                           │ (Validated Output)
                                           ▼
                               ┌───────────────────────┐
                               │  outputs/<case>.json  │ ──► traces/trace.jsonl
                               └───────────────────────┘
```

---

## 2. Agent Ownership & Tool Permissions

Nguyên tắc Least Privilege: Mỗi Agent chỉ được cấp quyền truy cập đúng tập công cụ MCP thuộc phạm vi chuyên môn của mình.

| Actor | Input | Trách nhiệm chính | Output / Handoff | Quyền gọi MCP Tools |
| :--- | :--- | :--- | :--- | :--- |
| **Coordinator** | `case: dict` từ `inputs/<case_id>.json` | Phân tích input, trích xuất `claimed_order_id`, phát event `task_assigned`, điều phối luồng thực thi song song của các Specialist Agents, tổng hợp kết quả bàn giao cho Policy Agent. | `CaseContext`, handoff payload sang Specialist Agents và Policy Agent | *Không gọi trực tiếp MCP tool* |
| **Order/Item Agent** | `case_id`, `order_id` | Thu thập thông tin đơn hàng, trạng thái (`order_status`), danh sách item, seller và ngữ cảnh sản phẩm. Trích xuất `order_ids`, `item_ids`, `seller_ids`. | `OrderEvidenceBundle` (dữ liệu đơn hàng, items, sellers, evidence refs) | `get_order`, `get_order_items`, `get_sellers`, `get_product_context` |
| **Payment Agent** | `case_id`, `order_id` | Thu thập dữ liệu thanh toán, timeline giao dịch (`captured`, `authorized`), phát hiện thanh toán trùng lặp (`duplicate_charge`), lệch giá trị (`payment_mismatch`), theo dõi tiến trình hoàn tiền (`refund_timeline`). | `PaymentEvidenceBundle` (dữ liệu payment, refund, payment references, evidence refs) | `get_order_payments`, `get_payment_timeline`, `get_refund_timeline` |
| **Shipment Agent** | `case_id`, `order_id` | Thu thập dữ liệu vận chuyển, so sánh mốc thời gian giao hàng thực tế vs dự kiến, phát hiện trễ hạn vận chuyển (`delivered_late`) và phân định trách nhiệm chậm trễ giữa người bán (seller handoff delay) và đơn vị vận chuyển (carrier delay). | `ShipmentEvidenceBundle` (dữ liệu shipment, shipment_ids, delay metrics, evidence refs) | `get_shipment_summary` |
| **Policy Agent** | Evidence Bundles từ 3 Specialist Agents, `policy_version`, danh sách `claims` | Tải chính sách sàn (`get_policy`), đối chiếu sự kiện thực tế với điều khoản chính sách, xác định `primary_issue`, tính toán bồi hoàn tài chính (`financial_resolution`), xếp hạng nguyên nhân gốc rễ (`ranked_causes`), chỉ định bên chịu trách nhiệm (`responsible_parties`), đánh giá từng claim (`claim_assessments`). | `DraftCaseOutput` bàn giao cho Verifier Agent | `get_policy`, `get_customer_history` |
| **Verifier Agent** | `DraftCaseOutput`, toàn bộ `evidence_refs` đã thu thập | Kiểm tra toàn bộ 7 bất biến xác thực (Verification Invariants): JSON Schema compliance, entity scope, evidence linkage, money consistency, resolution action uniqueness. Phê duyệt hoặc từ chối output. | `FinalCaseOutput` chuẩn schema `day09-l3a-output-v2` | *Không gọi MCP tool* |

---

## 3. A2A Protocol (Agent-to-Agent)

1. **Correlation & Message Envelope:**
   - Mọi thông điệp và lời gọi giữa các Agent đều mang `case_id` làm khóa tương quan (correlation key) duy nhất.
   - Các gói dữ liệu trao đổi giữa các Agent được định kiểu rõ ràng (Typed Dataclasses / Dictionaries) bao gồm metadata: `case_id`, `sender`, `timestamp`, `evidence_refs`, `data`.

2. **Handoff Conditions:**
   - **Phase 1 Handoff (Coordinator → Specialists):** Khi nhận được case hợp lệ, Coordinator kích hoạt đồng thời `OrderAgent`, `PaymentAgent`, và `ShipmentAgent`.
   - **Phase 2 Handoff (Specialists → Policy Agent):** Chỉ diễn ra khi cả 3 Specialist Agents đã hoàn tất việc thu thập bằng chứng hoặc trả về lỗi đã xử lý an toàn (graceful degradation).
   - **Phase 3 Handoff (Policy Agent → Verifier Agent):** Diễn ra khi Policy Agent đã đối chiếu chính sách và lập xong bản thảo `DraftCaseOutput`.
   - **Phase 4 Finalize (Verifier Agent → Coordinator):** Diễn ra khi Verifier xác nhận bản thảo đáp ứng 100% các tiêu chí bất biến.

3. **Observable Trace Events:**
   - Tuyệt đối không ghi nội dung suy luận bí mật (chain-of-thought) hoặc prompt vào trace.
   - Chỉ phát các sự kiện theo đúng `trace-event-v1.schema.json`:
     + `case_received` (Coordinator)
     + `task_assigned` (Coordinator → Specialist Agents)
     + `tool_result_consumed` (Từng Specialist Agent khi nhận evidence từ MCP Gateway)
     + `handoff` (Chuyển giao trạng thái giữa các tác tử)
     + `policy_decided` (Policy Agent khi chốt quyết định chính sách)
     + `verification_completed` (Verifier Agent khi hoàn tất kiểm tra)
     + `case_finalized` (Coordinator lưu file output)

---

## 4. Evidence Lifecycle

1. **Authentication & Validation:**
   - Mọi lời gọi công cụ MCP thông qua `EvidenceGateway` đều được xác thực bằng `COMPETITION_TEAM_API_KEY`.
   - Phản hồi từ MCP Gateway được bọc trong phong bì `mcp-evidence-response-v1` chứa `evidence_ref`, `result_hash`, `domain`, và `data`.
   - Gateway tự động validate phong bì với JSON Schema trước khi bàn giao cho Agent.

2. **Evidence Ownership & Scoping:**
   - Mỗi `evidence_ref` chỉ có giá trị trong phạm vi của đúng `case_id` đó. Tuyệt đối không tái sử dụng `evidence_ref` qua lại giữa các case khác nhau.
   - Toàn bộ `evidence_ref` từ các tool thành công được tích lũy vào `evidence_refs` của output và phát event `tool_result_consumed`.

3. **Claim Linkage:**
   - Từng claim trong `claim_assessments` phải liên kết trực tiếp với các `evidence_refs` làm cơ sở đưa ra phán quyết (`supported`, `unsupported`, `partially_supported`, `insufficient_evidence`).

---

## 5. Failure Policy & Resilience

Hệ thống tuân thủ nguyên tắc: *Không chuyển missing evidence thành dữ liệu phỏng đoán (Never hallucinate missing data).*

| Failure Scenario | Retry Policy | Fallback / Xử lý | Trace Event & Decision Code |
| :--- | :--- | :--- | :--- |
| **MCP Timeout / 5xx** | Tối đa 2 lần retry với Exponential Backoff (1s, 2s). Idempotent call. | Nếu sau retry vẫn lỗi, đánh dấu domain đó là unavailable, ghi nhận cảnh báo. | Ghi trace với `decision_code: "mcp_retry_exhausted"`. |
| **Entity Not Found (404 / Empty)** | Không retry (kết quả tất định). | Xem như thực thể không tồn tại (ví dụ: đơn hàng không có lịch sử hoàn tiền `get_refund_timeline`). | Gán trường dữ liệu là `None`/rỗng, tiếp tục quy trình đánh giá. |
| **Data Conflict (Xung đột nguồn)** | Không retry. | Ghi nhận vào danh sách `data_conflicts` của output với quy tắc ưu tiên: `authoritative_order` > `seller_record` > `customer_claim`. | Ghi nhận `data_conflicts` kèm `resolution_code`. |
| **Invalid Specialist Result** | 1 lần điều chỉnh fallback nội bộ. | Nếu dữ liệu thu thập không đủ để kết luận lỗi cụ thể, fallback về `primary_issue: "insufficient_evidence"`, `case_status: "needs_investigation"`, `confidence: 0.3`. | Ghi trace `policy_decided` với `decision_code: "insufficient_evidence"`. |

---

## 6. Verification Invariants (Quy tắc bất biến trước Finalize)

Trước khi xuất file `outputs/<case_id>.json`, Verifier Agent bắt buộc thực thi bộ kiểm tra chặn cổng (Hard Gates):

1. **Schema Compliance:** Output hợp lệ 100% theo `l3a-output-v2.schema.json` (không thừa field, định dạng regex khớp, enum chính xác).
2. **Case ID Uniformity:** `output["case_id"] == input["case_id"]`.
3. **Entity Scope Integrity:** Tất cả `order_ids`, `item_ids`, `seller_ids`, `payment_references`, `shipment_ids` trong `affected_entities` phải xuất hiện trong dữ liệu thực tế thu thập được từ MCP tools.
4. **Evidence Provenance & Ownership:** Mọi mã bằng chứng trong `evidence_refs` phải có tiền tố `ev_`, khớp độ dài 20–96 ký tự và được tạo ra trong phiên làm việc của chính case đó.
5. **Financial Reconcilation:**
   - Nếu `case_status == "action_required"` và có hoàn tiền: `recommended_refund_brl` phải bằng chính xác tổng `amount_brl` của tất cả các dòng trong `refund_lines`.
   - Nếu `case_status == "no_action"`: `recommended_refund_brl` phải bằng `0.0` và `refund_lines` rỗng.
6. **Action Consistency:** Các hành động trong `resolution_actions` không được trùng lặp (`uniqueItems: true`), có độ dài 1–80 ký tự và tương thích với `primary_issue`.
7. **Confidence Bounds:** `confidence` của `assessment` và từng `claim_assessment` phải nằm trong đoạn `[0.0, 1.0]`.

---

## 7. Reproducibility & Environment Bounds

- **Execution Environment:** Python 3.11+, MCP SDK 2.2.0, Pydantic 2.x, HTTPX2.
- **Model Parameters Constraint:** Chỉ sử dụng model $\le$ 10B parameters (Gemma-2-9B, Llama-3.1-8B qua Groq hoặc deterministic rule engine).
- **Concurrency & Resource Limits:**
  - Xử lý tuần tự hoặc kiểm soát semaphore tối đa 5 cases đồng thời để tôn trọng rate-limit của MCP Gateway.
  - Timeout tối đa mỗi case: 30 giây.
- **Zero Secret Leakage:** Tuyệt đối không in hay ghi `COMPETITION_TEAM_API_KEY` vào output JSON hay trace log.
