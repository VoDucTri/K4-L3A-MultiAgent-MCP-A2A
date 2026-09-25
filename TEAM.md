# DANH SÁCH THÀNH VIÊN & PHÂN CHIA CÔNG VIỆC
## Dự án: K4 L3A — Multi-Agent MCP + A2A

---

### 📌 THÔNG TIN NHÓM
- **Tên nhóm:** `K4-Team79-A Trí`
- **Repository:** [https://github.com/VoDucTri/K4-L3A-MultiAgent-MCP-A2A](https://github.com/VoDucTri/K4-L3A-MultiAgent-MCP-A2A)
- **Mã phân ban:** L3A (E-commerce Dispute & Refund Multi-Agent Resolution)

---

### 👥 DANH SÁCH THÀNH VIÊN VÀ PHÂN CÔNG CÔNG VIỆC

| STT | Họ và Tên | Mã Sinh Viên (MSSV) | Vai trò | Phân chia công việc theo yêu cầu đề thi |
| :---: | :--- | :---: | :---: | :--- |
| **1** | **Võ Đức Trí** | **2A202602603** | **Trưởng nhóm (Leader)** | • **Orchestrator**: Thiết kế và xây dựng bộ điều phối luồng A2A (`CoordinatorRouter`).<br>• Xây dựng `PolicyAgent` phân xử điều khoản bồi hoàn tài chính và hiệu chuẩn độ tự tin (Calibration).<br>• Quản lý Git repository, kiểm soát nộp bài chung cho nhóm. |
| **2** | **Ngọ Doãn Ngọc** | **2A202602635** | **Thành viên** | • **Viết tay chân kết nối MCP**: Cấu hình và tối ưu hóa `EvidenceGateway` kết nối MCP Gateway, xử lý SSL, timeout và backoff.<br>• **Thiết kế các Subagent**: Xây dựng `OrderAgent` (truy vấn đơn hàng, items, sellers) và `PaymentAgent` (truy vấn payment, timeline, refund). |
| **3** | **Đỗ Hoàng Nam Khánh** | **2A202602423** | **Thành viên** | • **Thiết kế Subagent**: Xây dựng `ShipmentAgent` phân định trách nhiệm chậm trễ vận chuyển (seller vs carrier).<br>• **Valid lại log, schema, contract**: Kiểm soát bộ kiểm thử (`pytest`), thẩm định JSON Schema output, hợp thức hóa Observable Trace (`trace-event-v1`) và xây dựng `VerifierAgent`. |

---

### 📋 CHECKLIST TUÂN THỦ NGUYÊN TẮC THI ĐẤU (THEO HƯỚNG DẪN)

1. [x] **Check có gitkeep không:** Đã kiểm tra sạch sẽ, file `submission.zip` không chứa `.gitkeep` hay thư mục ẩn nào.
2. [x] **Check đúng input không hay tự gen ra:** 100% sử dụng input chính thức từ bộ đề `l3a-inputs-*.zip` (`case-set.json` và 100 files `inputs/L3A_CASE_*.json`), không tự sinh input.
3. [x] **Check định dạng output:** Tuân thủ chuẩn 100% theo schema `day09-l3a-output-v2.schema.json`.
4. [x] **Check output schema trong readme:** Đã đồng bộ với schema contract trong thư mục `contracts/schemas/`.
5. [x] **Ràng buộc Model:** Toàn bộ hệ thống chạy trên kiến trúc tác tử tất định (Deterministic Rule Engine & Policy Parser), 0% vi phạm giới hạn 10B parameters, không rò rỉ secret key vào output và trace log.
6. [x] **Quy định nộp bài:** Trưởng nhóm nộp đại diện và các thành viên thực hiện nộp xác nhận bài cá nhân trên cổng thi.
