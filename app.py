import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
import io
import os

# --- 設定 ---
st.set_page_config(page_title="集金袋メーカー", layout="wide")

# 公式フォント（IPAゴシック）を使用
FONT_FILE = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
FONT_NAME = "IPAGothic"

# フォント登録
font_ready = False
try:
    if os.path.exists(FONT_FILE):
        pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_FILE))
        font_ready = True
    else:
        st.warning(f"日本語フォントが見つかりません。")
except Exception as e:
    st.error(f"フォント登録エラー: {e}")

# --- タイトルと説明 ---
st.title("💰 スポ少会計専用：集金袋ラベルメーカー")
st.markdown("名簿を入力・修正して、長形4号封筒に貼れるサイズのPDFを一括作成します。")

# --- サイドバー：設定 ---
st.sidebar.header("1. 基本設定")
fiscal_year = st.sidebar.number_input("年度", value=2025, step=1)
default_fee = st.sidebar.number_input("団費（円）", value=3000, step=100)

st.sidebar.subheader("「その他」欄の項目名 (最大6つ)")
other_labels = []
for i in range(6):
    val = st.sidebar.text_input(f"項目 {i+1}", value=f"臨時集金{i+1}" if i < 2 else "", key=f"other_{i}")
    other_labels.append(val)

# --- データ管理 ---
st.header("2. 名簿の編集")

if "member_df" not in st.session_state:
    data = {
        "名前": ["山田 太郎", "鈴木 次郎", "佐藤 花子"],
        "月謝": [default_fee, default_fee, default_fee],
        "備考": ["", "", "兄弟割引"]
    }
    st.session_state.member_df = pd.DataFrame(data)

uploaded_file = st.file_uploader("CSVファイルを読み込む", type="csv")
if uploaded_file:
    try:
        df_input = pd.read_csv(uploaded_file)
        if "名前" not in df_input.columns:
            st.error("CSVには必ず「名前」列が必要です")
        else:
            if "月謝" not in df_input.columns:
                df_input["月謝"] = default_fee
            st.session_state.member_df = df_input
            st.success("CSVを読み込みました！")
    except Exception as e:
        st.error(f"読み込みエラー: {e}")

edited_df = st.data_editor(
    st.session_state.member_df,
    num_rows="dynamic", 
    use_container_width=True
)

csv_export = edited_df.to_csv(index=False).encode('utf-8_sig')
st.download_button(
    label="名簿をCSVで保存",
    data=csv_export,
    file_name="member_list.csv",
    mime="text/csv",
)

# --- PDF生成ロジック ---
def create_pdf(dataframe, year, other_items):
    buffer = io.BytesIO()
    # A4横向き (297mm x 210mm)
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    
    # ラベルサイズ指定 (縦20cm x 横8.5cm)
    label_w = 85 * mm
    label_h = 200 * mm
    
    # A4横幅 297mm に対して 85mm x 3枚 = 255mm
    # 余白 (297 - 255) / 2 = 21mm (左右)
    margin_x = (297 * mm - (label_w * 3)) / 2
    
    # A4縦幅 210mm に対して 200mm
    # 余白 (210 - 200) / 2 = 5mm (上下)
    margin_y = (210 * mm - label_h) / 2
    
    rows = dataframe.to_dict('records')
    
    for i, row in enumerate(rows):
        col_idx = i % 3 # 0, 1, 2列目
        
        # 3つごとに改ページ (最初のページ以外)
        if i > 0 and col_idx == 0:
            c.showPage()
        
        # 現在のラベルの左下座標
        x = margin_x + (col_idx * label_w)
        y = margin_y
        
        # --- 外枠 ---
        c.setLineWidth(1)
        c.setStrokeColor(colors.black)
        c.rect(x, y, label_w, label_h)
        
        title_font = FONT_NAME if font_ready else "Helvetica"
        
        # ※座標は「左下(x,y)」を基準に、「上方向(+mm)」へ配置していきます
        
        # 1. 年度タイトル (上から12mm)
        c.setFont(title_font, 14)
        c.drawCentredString(x + label_w/2, y + label_h - 12*mm, f"{year}年度 集金袋")
        
        # 2. 名前 (上から22mm)
        c.setFont(title_font, 16)
        c.drawCentredString(x + label_w/2, y + label_h - 22*mm, f"{row['名前']} 殿")

        # 3. 団費 (上から30mm)
        c.setFont(title_font, 11)
        fee_amount = int(row.get('月謝', default_fee))
        c.drawCentredString(x + label_w/2, y + label_h - 30*mm, f"団費: ¥{fee_amount:,}")
        
        # --- 12ヶ月の表 ---
        row_h = 8 * mm
        
        # 表の開始位置 (上から35mm地点からスタート)
        table_top_y = y + label_h - 35*mm
        
        col_w_month = 15 * mm
        col_w_amount = 25 * mm
        col_w_stamp = 30 * mm # 合計70mm幅
        
        total_w = col_w_month + col_w_amount + col_w_stamp
        table_x = x + (label_w - total_w) / 2
        
        # ヘッダー
        c.setFont(title_font, 10)
        c.rect(table_x, table_top_y - row_h, col_w_month, row_h)
        c.drawCentredString(table_x + col_w_month/2, table_top_y - row_h + 2.5*mm, "月")
        
        c.rect(table_x + col_w_month, table_top_y - row_h, col_w_amount, row_h)
        c.drawCentredString(table_x + col_w_month + col_w_amount/2, table_top_y - row_h + 2.5*mm, "金額")
        
        c.rect(table_x + col_w_month + col_w_amount, table_top_y - row_h, col_w_stamp, row_h)
        c.drawCentredString(table_x + col_w_month + col_w_amount + col_w_stamp/2, table_top_y - row_h + 2.5*mm, "受領印")
        
        # 4月〜3月ループ
        months = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]
        current_y = table_top_y - row_h
        
        for m in months:
            current_y -= row_h
            
            # 月
            c.rect(table_x, current_y, col_w_month, row_h)
            c.drawCentredString(table_x + col_w_month/2, current_y + 2.5*mm, f"{m}月")
            
            # 金額（空欄）
            c.rect(table_x + col_w_month, current_y, col_w_amount, row_h)
            
            # 印鑑欄
            c.rect(table_x + col_w_month + col_w_amount, current_y, col_w_stamp, row_h)

        # --- その他の欄 ---
        table_bottom_y = current_y
        other_header_y = table_bottom_y - 8*mm
        
        c.setFont(title_font, 10)
        c.drawString(table_x, other_header_y + 2*mm, "■ 臨時集金など")
        
        other_row_h = 8 * mm
        c.setFont(title_font, 8)
        
        current_other_y = other_header_y
        
        # 【修正箇所】臨時集金欄の幅設定
        # 全体70mmのうち、右側をハンコ用(25mm)にし、残りを左側(45mm)にする
        other_w_right = 25 * mm
        other_w_left = total_w - other_w_right # = 45mm
        
        for k in range(6):
            current_other_y -= other_row_h
            label_text = other_items[k] if k < len(other_items) else ""
            
            # 項目名エリア（左側：広く）
            c.rect(table_x, current_other_y, other_w_left, other_row_h)
            c.setFont(title_font, 8)
            # 文字数が多い場合はフォントを小さく調整
            if len(label_text) > 10:
                 c.setFont(title_font, 6)
            elif len(label_text) > 7:
                 c.setFont(title_font, 7)
            
            c.drawString(table_x + 2*mm, current_other_y + 2.5*mm, label_text)
            
            # 受領印エリア（右側：狭く）
            c.rect(table_x + other_w_left, current_other_y, other_w_right, other_row_h)

    c.save()
    buffer.seek(0)
    return buffer

st.divider()
st.header("3. PDF作成")

if st.button("集金袋ラベルPDFを作成する", type="primary"):
    if len(edited_df) == 0:
        st.warning("名簿データがありません。")
    else:
        pdf_data = create_pdf(edited_df, fiscal_year, other_labels)
        st.success(f"{len(edited_df)}名分のPDFを作成しました！（A4横 / 3列）")
        st.download_button(
            label="PDFをダウンロード",
            data=pdf_data,
            file_name=f"shukin_bukuro_{fiscal_year}.pdf",
            mime="application/pdf"
        )