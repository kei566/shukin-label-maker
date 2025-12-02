import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, portrait
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
import io
import os
import requests

# --- 設定 ---
st.set_page_config(page_title="集金袋メーカー", layout="wide")

# 日本語フォントのセットアップ（IPAexゴシックを自動ダウンロード）
FONT_URL = "https://moji.or.jp/wp-content/ipafont/IPAexfont/ipaexg00401.ttf"
FONT_FILE = "ipaexg.ttf"

@st.cache_resource
def setup_font():
    if not os.path.exists(FONT_FILE):
        # フォントがなければダウンロード（少し時間がかかります）
        try:
            response = requests.get(FONT_URL)
            if response.status_code == 200:
                with open(FONT_FILE, "wb") as f:
                    f.write(response.content)
            else:
                st.error("フォントのダウンロードに失敗しました。")
                return False
        except:
            # 代替URL（GitHubなどの安定したソースがあればそちらに切り替え推奨）
            st.warning("フォントのダウンロード中にエラーが発生しました。")
            return False
            
    pdfmetrics.registerFont(TTFont('IPAexGothic', FONT_FILE))
    return True

font_ready = setup_font()

# --- タイトルと説明 ---
st.title("💰 スポ少会計専用：集金袋ラベルメーカー")
st.markdown("名簿を入力・修正して、長形4号封筒に貼れるサイズのPDFを一括作成します。")

# --- サイドバー：設定 ---
st.sidebar.header("1. 基本設定")
fiscal_year = st.sidebar.number_input("年度", value=2025, step=1)
default_fee = st.sidebar.number_input("基本の月謝（円）", value=3000, step=100)

st.sidebar.subheader("「その他」欄の項目名 (最大6つ)")
other_labels = []
for i in range(6):
    val = st.sidebar.text_input(f"項目 {i+1}", value=f"臨時集金{i+1}" if i < 2 else "", key=f"other_{i}")
    other_labels.append(val)

# --- データ管理 ---
st.header("2. 名簿の編集")

# データの初期化
if "member_df" not in st.session_state:
    # サンプルデータ
    data = {
        "名前": ["山田 太郎", "鈴木 次郎", "佐藤 花子"],
        "月謝": [default_fee, default_fee, default_fee],
        "備考": ["", "", "兄弟割引"]
    }
    st.session_state.member_df = pd.DataFrame(data)

# CSVインポート
uploaded_file = st.file_uploader("CSVファイルを読み込む（以前出力したCSVも可）", type="csv")
if uploaded_file:
    try:
        df_input = pd.read_csv(uploaded_file)
        # 必要な列があるか確認、なければ追加
        if "名前" not in df_input.columns:
            st.error("CSVには必ず「名前」列が必要です")
        else:
            if "月謝" not in df_input.columns:
                df_input["月謝"] = default_fee
            st.session_state.member_df = df_input
            st.success("CSVを読み込みました！")
    except Exception as e:
        st.error(f"読み込みエラー: {e}")

# データエディタ（ここで修正可能）
edited_df = st.data_editor(
    st.session_state.member_df,
    num_rows="dynamic", # 行の追加削除を許可
    use_container_width=True
)

# CSVエクスポート（保存用）
csv_export = edited_df.to_csv(index=False).encode('utf-8_sig')
st.download_button(
    label="現在の名簿をCSVで保存（次回用）",
    data=csv_export,
    file_name="member_list.csv",
    mime="text/csv",
)

# --- PDF生成ロジック ---
def create_pdf(dataframe, year, other_items):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=portrait(A4))
    
    # A4サイズ: 210mm x 297mm
    # 長形4号(90x205)に貼るため、ラベルサイズを幅85mm x 高さ190mm程度とする
    # A4に横に2つ並べる（左右マージン考慮）
    
    label_w = 90 * mm
    label_h = 240 * mm # 少し縦長にしてたっぷり書けるようにする
    
    # 開始位置（左側）
    x_left = 10 * mm
    # 開始位置（右側）
    x_right = 110 * mm
    y_start = 280 * mm # 上からスタート
    
    rows = dataframe.to_dict('records')
    
    for i, row in enumerate(rows):
        # 左か右かを判定
        is_left = (i % 2 == 0)
        
        # ページ送り判定（偶数番目のときに、それが0番目でなければ）
        if i > 0 and i % 2 == 0:
            c.showPage() # 次のページへ
            
        x = x_left if is_left else x_right
        y = y_start
        
        # --- 枠線 ---
        c.setLineWidth(1)
        c.setStrokeColor(colors.black)
        c.rect(x, y - label_h, label_w, label_h)
        
        # --- タイトル ---
        if font_ready:
            c.setFont("IPAexGothic", 14)
        c.drawCentredString(x + label_w/2, y - 15*mm, f"{year}年度 集金袋")
        
        # --- 名前 ---
        c.setFont("IPAexGothic", 18)
        c.drawCentredString(x + label_w/2, y - 30*mm, f"{row['名前']} 殿")
        
        # --- 12ヶ月の表 ---
        # 表の開始位置
        table_y = y - 45*mm
        row_h = 11 * mm # 行の高さ
        col_w_month = 15 * mm
        col_w_amount = 25 * mm
        col_w_stamp = 35 * mm
        
        total_w = col_w_month + col_w_amount + col_w_stamp
        table_x = x + (label_w - total_w) / 2 # 中央寄せ
        
        # ヘッダー
        c.setFont("IPAexGothic", 10)
        c.rect(table_x, table_y, col_w_month, row_h)
        c.drawString(table_x + 2*mm, table_y + 3*mm, "月")
        
        c.rect(table_x + col_w_month, table_y, col_w_amount, row_h)
        c.drawString(table_x + col_w_month + 2*mm, table_y + 3*mm, "金額")
        
        c.rect(table_x + col_w_month + col_w_amount, table_y, col_w_stamp, row_h)
        c.drawString(table_x + col_w_month + col_w_amount + 2*mm, table_y + 3*mm, "受領印")
        
        # 4月〜3月までループ
        months = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]
        for idx, m in enumerate(months):
            current_y = table_y - (idx + 1) * row_h
            
            # 月
            c.rect(table_x, current_y, col_w_month, row_h)
            c.drawCentredString(table_x + col_w_month/2, current_y + 3*mm, f"{m}月")
            
            # 金額（薄い文字で予定額を入れておく）
            c.rect(table_x + col_w_month, current_y, col_w_amount, row_h)
            c.setFillColor(colors.gray)
            amount_str = f"¥{int(row.get('月謝', default_fee)):,}"
            c.drawCentredString(table_x + col_w_month + col_w_amount/2, current_y + 3*mm, amount_str)
            c.setFillColor(colors.black)
            
            # 印鑑欄
            c.rect(table_x + col_w_month + col_w_amount, current_y, col_w_stamp, row_h)

        # --- その他の欄 ---
        other_y = table_y - (13 * row_h) - 10*mm # 表の下にスペースを空ける
        c.setFont("IPAexGothic", 12)
        c.drawString(table_x, other_y + 5*mm, "■ 臨時集金など")
        
        other_row_h = 10 * mm
        # ヘッダー
        c.setFont("IPAexGothic", 8)
        
        # その他の欄を描画 (入力されたラベルを使用)
        active_others = [l for l in other_items if l.strip() != ""]
        # 空欄を含めて6行確保するか、入力分だけ確保するか。ここでは6行固定にします。
        for k in range(6):
            oy = other_y - (k * other_row_h)
            
            # 項目名が入っていればそれを表示、なければ空欄
            label_text = other_items[k] if k < len(other_items) else ""
            
            # 項目名エリア
            c.rect(table_x, oy, 30*mm, other_row_h)
            c.setFont("IPAexGothic", 9)
            c.drawString(table_x + 2*mm, oy + 3*mm, label_text)
            
            # 金額/印鑑エリア（フリースペース）
            c.rect(table_x + 30*mm, oy, total_w - 30*mm, other_row_h)

    c.save()
    buffer.seek(0)
    return buffer

# --- 生成ボタン ---
st.divider()
st.header("3. PDF作成")

if st.button("集金袋ラベルPDFを作成する", type="primary"):
    if len(edited_df) == 0:
        st.warning("名簿データがありません。")
    else:
        pdf_data = create_pdf(edited_df, fiscal_year, other_labels)
        st.success(f"{len(edited_df)}名分のPDFを作成しました！")
        
        st.download_button(
            label="PDFをダウンロード",
            data=pdf_data,
            file_name=f"shukin_bukuro_{fiscal_year}.pdf",
            mime="application/pdf"
        )