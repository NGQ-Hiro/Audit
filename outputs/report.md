# Báo cáo đánh giá chấp nhận khách hàng kiểm toán

**Khách hàng:** Công ty X (dữ liệu thật 2024) | **Ngành:** Thương mại | **Kỳ:** 2024-01-01 đến 2024-12-31

## 1. Kết luận
- Điểm rủi ro: **29.1/100**
- Kết luận: **Chấp nhận**
- Quy tắc chặn: không kích hoạt

Lý do chính:
- Rủi ro gian lận (kiểm tra bút toán): 38/100 (đóng góp 11.4 điểm)
- Rủi ro báo cáo (cut-off, doanh thu, phải thu): 47/100 (đóng góp 7.1 điểm)
- Yếu tố định tính: 43/100 (đóng góp 4.3 điểm)

Điều kiện / hành động đề xuất:
- Rủi ro báo cáo (cut-off, doanh thu, phải thu) (47/100): Tăng thủ tục cut-off cuối kỳ, gửi thư xác nhận công nợ phải thu, tham gia kiểm kê hàng tồn kho.
- Yếu tố định tính (43/100): Tìm hiểu thêm về quản trị, thư giải trình của Ban Giám đốc, cân nhắc phí kiểm toán phù hợp với rủi ro.

## 2. Điểm theo nhóm
| nhom | diem | trong_so |
|---|---|---|
| data_quality | 16.67 | 0.1500 |
| fraud | 38.03 | 0.3000 |
| financial | 12.50 | 0.3000 |
| reporting | 47.27 | 0.1500 |
| qualitative | 43.33 | 0.1000 |

## 3. Toàn vẹn dữ liệu
Có 8/18 chỉ tiêu cần chú ý. Mức độ tin cậy của dữ liệu: thấp.
Chứng từ INO2402001 không cân Nợ/Có, chênh lệch 812,142

34 chứng từ số dư đầu kỳ (ghi ngày đầu kỳ, lệch một vế do nhập số dư) được báo cáo riêng, không tính vào quy tắc chặn "sổ không cân".

| chi_tieu | gia_tri | danh_gia |
|---|---|---|
| Số dòng | 100626 | Đạt |
| Số chứng từ | 17123 | Đạt |
| Từ ngày | 2024-01-01 | Đạt |
| Đến ngày | 2024-12-31 | Đạt |
| Số tháng thiếu dữ liệu | 0 | Đạt |
| Tổng phát sinh Nợ | 4,549,576,132,250.58 | Đạt |
| Tổng phát sinh Có | 4,549,575,320,108.57 | Đạt |
| Chênh lệch Nợ - Có toàn sổ | 812,142.01 | Cần chú ý |
| Chứng từ không cân (không tính bút toán số dư đầu kỳ) | 1 | Cần chú ý |
| Chứng từ số dư đầu kỳ lệch một vế (OD, NKO, OI, OV; ghi ngày đầu kỳ) | 34 | Đạt |
| Dòng có TK ngoài danh mục | 0 | Đạt |
| Dòng thiếu ngày/TK/số tiền | 2 | Cần chú ý |
| Dòng thiếu số chứng từ | 128 | Cần chú ý |
| Dòng số tiền âm | 5156 | Cần chú ý |
| Dòng số tiền bằng 0 | 1579 | Cần chú ý |
| Dòng ghi sổ ngoài kỳ kế toán | 0 | Đạt |
| Dòng ngày ghi sổ lệch ngày CT > 30 ngày | 376 | Cần chú ý |
| Tài khoản lệch so với bảng CĐSPS của khách hàng | 1 | Cần chú ý |

Tài khoản lệch so với bảng CĐSPS của khách hàng (đã đối chiếu với chứng từ không cân ở mục JE01):

| tk | no | co | ps_no | ps_co | lech_no | lech_co |
|---|---|---|---|---|---|---|
| 6418 | 28,825,927,296.24 | 28,825,115,154.20 | 28,825,115,154.20 | 28,825,115,154.20 | 812,142.04 | 0.00 |

## 4. Mức trọng yếu
| tieu_chi | co_so | ty_le | so_tien | duoc_chon |
|---|---|---|---|---|
| pbt | 11,320,963,311.93 | 0.0500 | 570,000,000.00 |  |
| revenue | 475,601,669,832.53 | 0.0050 | 2,400,000,000.00 | x |
| assets | 203,891,847,825.14 | 0.0100 | 2,000,000,000.00 |  |
| Mức trọng yếu thực hiện |  | 0.7500 | 1,800,000,000.00 |  |
| Ngưỡng sai sót không đáng kể |  | 0.0500 | 120,000,000.00 |  |

Lý do chọn tiêu chí `revenue`: Doanh thu ổn định hơn lợi nhuận với doanh nghiệp thương mại; lợi nhuận mỏng nên 5% LNTT dễ sai lệch.

## 5. Kiểm tra bút toán
| ma_thu_tuc | thu_tuc | so_luong | gia_tri | so_rui_ro_cao | ghi_chu |
|---|---|---|---|---|---|
| JE01 | Chứng từ không cân Nợ/Có | 35 | 136,923,479,064.04 | 35 |  |
| JE02 | Chứng từ trùng lặp | 11017 | 8,151,364,415.06 | 0 |  |
| JE03 | Khoảng trống/nhảy số chứng từ | 454 | 0.00 | 0 |  |
| JE04 | Bút toán vào cuối tuần / ngày lễ | 2238 | 472,097,951,247.63 | 50 |  |
| JE05 | Nhập liệu ngoài giờ làm việc | 0 | 0.00 | 0 | không có dữ liệu giờ nhập |
| JE06 | Số tiền tròn | 1046 | 654,826,000,000.00 | 80 |  |
| JE07 | Số tiền ngay dưới ngưỡng phê duyệt | 175 | 53,600,650,264.76 | 0 |  |
| JE08 | Bút toán lớn sát ngày khóa sổ | 34 | 165,568,229,608.00 | 18 |  |
| JE09 | Cặp tài khoản đối ứng bất thường | 0 | 0.00 | 0 |  |
| JE10 | Người lập lạ hoặc rất ít bút toán | 0 | 0.00 | 0 | không có dữ liệu người lập |
| JE11 | Diễn giải trống hoặc mơ hồ | 0 | 0.00 | 0 |  |
| JE12 | Đối tượng chỉ phát sinh 1 lần, giá trị lớn | 4 | 6,444,946,696.00 | 1 |  |
| JE13 | Ngoại lệ thống kê (IQR trên log, theo TK) | 20 | 42,988,961,424.00 | 6 |  |
| JE14 | Kiểm định Benford chữ số đầu | 0 | 0.00 | 0 |  |

10 phát hiện rủi ro cao nhất:
| ma_thu_tuc | so_ct | ngay | tk | so_tien | mo_ta | muc_do |
|---|---|---|---|---|---|---|
| JE01 | OD23120112 | 2024-01-01 | 221 | 40,000,000,000.00 | Lệch Nợ/Có 40,000,000,000 | Cao |
| JE01 | OD23120113 | 2024-01-01 | 2292 | 34,266,325,889.00 | Lệch Nợ/Có 34,266,325,889 | Cao |
| JE08 | GL24120108 | 2024-12-31 | 1541,6323 | 30,646,537,035.00 | Bút toán lớn 30,646,537,035 ngày 31/12/2024 gần khóa sổ | Cao |
| JE04 | CE240700033 | 2024-06-30 | 1541,621,622,6278 | 29,562,322,008.00 | Ghi sổ ngày 30/06/2024 (cuối tuần) | Cao |
| JE04 | GL24060085 | 2024-06-30 | 1541,6323 | 28,120,808,026.00 | Ghi sổ ngày 30/06/2024 (cuối tuần) | Cao |
| JE01 | NKO2401001 | 2024-01-01 | 1561 | 26,402,766,842.00 | Lệch Nợ/Có 26,402,766,842 | Cao |
| JE04 | NKO2401001 | 2024-01-01 | 1561 | 26,402,766,842.00 | Ghi sổ ngày 01/01/2024 (ngày lễ) | Cao |
| JE08 | CE250100059 | 2024-12-31 | 1541,5111,5211,5212,5213,621 | 26,208,469,272.00 | Bút toán lớn 26,208,469,272 ngày 31/12/2024 gần khóa sổ | Cao |
| JE04 | AV24080003 | 2024-08-03 | 1561,3311,33312,33319,33321 | 24,240,841,799.00 | Ghi sổ ngày 03/08/2024 (cuối tuần) | Cao |
| JE06 | C91022407014 | 2024-07-12 | 1121 | 18,000,000,000.00 | Số tiền tròn 18,000,000,000 | Cao |

Kiểm định Benford (MAD Nigrini: <0.006 chặt, <0.012 chấp nhận, <0.015 biên, còn lại không phù hợp; chi2 tới hạn 15.507):
| nhom | n | mad | chi2 | muc_phu_hop |
|---|---|---|---|---|
| Toàn sổ | 93327 | 0.0060 | 334.33 | acceptable |
| Doanh thu | 4457 | 0.0054 | 18.97 | close |
| Chi phí | 37353 | 0.0063 | 151.36 | acceptable |

## 6. Chỉ số tài chính
| nhom | chi_so | gia_tri | danh_gia | ghi_chu |
|---|---|---|---|---|
| Thanh khoản | Hệ số thanh toán hiện hành | 4.56 | Tốt |  |
| Thanh khoản | Hệ số thanh toán nhanh | 2.44 | Tốt |  |
| Thanh khoản | Hệ số thanh toán tiền mặt | 0.3932 | Tốt |  |
| Cơ cấu vốn | Nợ phải trả / Tổng tài sản | 0.1954 | Tốt |  |
| Cơ cấu vốn | Nợ phải trả / Vốn chủ sở hữu (D/E) | 0.2428 | Tốt |  |
| Cơ cấu vốn | Khả năng trả lãi vay (EBIT / lãi vay) | 3.79 | Tốt |  |
| Hiệu quả hoạt động | Số ngày thu tiền (DSO) | 40.71 | Tốt |  |
| Hiệu quả hoạt động | Số ngày tồn kho (DIO) | 67.89 | Cần chú ý |  |
| Hiệu quả hoạt động | Số ngày phải trả (DPO) | 16.17 | Tham khảo |  |
| Hiệu quả hoạt động | Chu kỳ chuyển đổi tiền mặt (CCC) | 92.43 | Cần chú ý |  |
| Hiệu quả hoạt động | Vòng quay tổng tài sản | 2.41 | Tốt |  |
| Khả năng sinh lời | Biên lợi nhuận gộp | 0.1583 | Cần chú ý |  |
| Khả năng sinh lời | Biên lợi nhuận ròng | 0.0238 | Cần chú ý |  |
| Khả năng sinh lời | ROA | 0.0573 | Tốt |  |
| Khả năng sinh lời | ROE | 0.0715 | Cần chú ý |  |
| Cảnh báo | Altman Z'' (không có hằng số) | 9.34 | Tốt |  |
| Cảnh báo | Tỷ lệ dồn tích (accruals) | -0.0033 | Tốt |  |

Lưu ý: tài khoản lưỡng tính (131, 331...) được trình bày theo số dư thuần theo tài khoản. Chênh lệch BCĐKT: 812,142.

## 7. Phân tích độ nhạy (±20%)
| kich_ban | diem | ket_luan | doi_ket_luan | ket_luan_theo_diem | doi_theo_diem |
|---|---|---|---|---|---|
| Cơ sở | 29.10 | Chấp nhận | False | Chấp nhận | False |
| Trọng số data_quality -20% | 29.50 | Chấp nhận | False | Chấp nhận | False |
| Trọng số data_quality +20% | 28.70 | Chấp nhận | False | Chấp nhận | False |
| Trọng số fraud -20% | 28.50 | Chấp nhận | False | Chấp nhận | False |
| Trọng số fraud +20% | 29.60 | Chấp nhận | False | Chấp nhận | False |
| Trọng số financial -20% | 30.10 | Chấp nhận | False | Chấp nhận | False |
| Trọng số financial +20% | 28.10 | Chấp nhận | False | Chấp nhận | False |
| Trọng số reporting -20% | 28.50 | Chấp nhận | False | Chấp nhận | False |
| Trọng số reporting +20% | 29.60 | Chấp nhận | False | Chấp nhận | False |
| Trọng số qualitative -20% | 28.80 | Chấp nhận | False | Chấp nhận | False |
| Trọng số qualitative +20% | 29.40 | Chấp nhận | False | Chấp nhận | False |
| Ngưỡng tín hiệu -20% | 32.80 | Chấp nhận | False | Chấp nhận | False |
| Ngưỡng kết luận -20% | 29.10 | Chấp nhận | False | Chấp nhận | False |
| Ngưỡng tín hiệu +20% | 26.90 | Chấp nhận | False | Chấp nhận | False |
| Ngưỡng kết luận +20% | 29.10 | Chấp nhận | False | Chấp nhận | False |

Kết luận cuối có đổi trong 0/15 kịch bản.
Kết luận chỉ theo điểm (bỏ quy tắc chặn) có đổi trong 0/15 kịch bản.
Quy tắc chặn giữ kết luận cuối ở mức tối thiểu "Chấp nhận có điều kiện" nên cột "theo điểm" mới cho thấy độ nhạy thật của điểm số.

## 8. Giả định
- Yếu tố định tính do nhóm tự đánh giá: {'industry_risk': 40, 'governance': 50, 'management_integrity': 40} (0 = rủi ro thấp, 100 = cao).
- Ngưỡng chỉ số trong `config/benchmarks.json` là ngưỡng kinh nghiệm, cần thay bằng số liệu ngành có nguồn.
- Danh sách ngày lễ trong `config/params.json` cần được kiểm tra lại.
- Chứng từ số dư đầu kỳ nhận diện theo tiền tố trong `opening_prefixes` và ngày ghi sổ = ngày đầu kỳ.
- Tài khoản 131/331 trình bày theo số dư thuần; bút toán kết chuyển cuối kỳ bị loại khỏi doanh thu/chi phí bằng `flag_closing`.

## 9. Hạn chế dữ liệu
| Hạn chế | Ảnh hưởng |
|---|---|
| Sổ không có giờ nhập và người lập | JE05, JE10 bỏ qua; biểu đồ 04, 05 dùng thay thế (thứ trong tuần x tháng; tiền tố số chứng từ) |
| Cột TK đối ứng gần như trống | JE09 yếu |
| Chỉ có dữ liệu 1 năm | Không phân tích xu hướng, không tính Beneish M-score; số dư đầu kỳ lấy từ sổ và bảng CĐSPS |
| Số chứng từ có nhiều định dạng | JE03 chỉ kiểm tra định dạng "chuỗi + YYMM + số thứ tự"; dòng thiếu số chứng từ gộp chung |
| Tên và ngành khách hàng chưa có | Dùng tên giả định; benchmark ngành chưa có nguồn |
