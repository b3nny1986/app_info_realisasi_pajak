import streamlit as st
import sqlite3
import pandas as pd
import altair as alt

# --- DB Setup ---
conn = sqlite3.connect("pajak.db")
cur = conn.cursor()

# Create tables if they don't exist
cur.execute("""
CREATE TABLE IF NOT EXISTS admin (
    username TEXT PRIMARY KEY,
    password TEXT
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS jenis_pajak (
    jenis TEXT PRIMARY KEY
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS target (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tahun INTEGER,
    jenis TEXT,
    jumlah REAL
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS realisasi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tahun INTEGER,
    bulan INTEGER,
    jenis TEXT,
    jumlah REAL
)
""")
conn.commit()

# Insert default admin and tax types if tables are empty
cur.execute("SELECT COUNT(*) FROM admin")
if cur.fetchone()[0] == 0:
    cur.execute("INSERT INTO admin (username, password) VALUES (?, ?)", ("admin", "admin123"))
    conn.commit()

cur.execute("SELECT COUNT(*) FROM jenis_pajak")
if cur.fetchone()[0] == 0:
    default_jenis = ["PKB", "BBNKB", "PAP", "PAB", "Opsen MBLB"]
    for jenis in default_jenis:
        cur.execute("INSERT INTO jenis_pajak (jenis) VALUES (?)", (jenis,))
    conn.commit()

# --- UI Setup ---
st.set_page_config(page_title="Sistem Informasi Pajak Daerah", layout="wide")
st.title("📊 Sistem Informasi Pajak Daerah UPTD PPRD PPU")

# Initialize session state for login
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# --- User Interface Logic ---
if not st.session_state['logged_in']:
    # --- Login Section ---
    st.sidebar.subheader("Login Admin")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Login"):
        cur.execute("SELECT * FROM admin WHERE username = ? AND password = ?", (username, password))
        if cur.fetchone():
            st.session_state['logged_in'] = True
            st.sidebar.success("Login berhasil!")
            st.rerun()
        else:
            st.sidebar.error("Username atau password salah.")

    # --- Public User Menu (for non-logged-in users) ---
    st.subheader("📈 Visualisasi Pajak Daerah")
    df_target = pd.read_sql("SELECT tahun, jenis, jumlah FROM target", conn)
    df_real = pd.read_sql("SELECT tahun, bulan, jenis, jumlah FROM realisasi", conn)
    
    # Check if data exists
    if not df_target.empty and not df_real.empty:
        # Get unique years and tax types
        all_years = sorted(list(set(df_target['tahun'].unique()) | set(df_real['tahun'].unique())), reverse=True)
        all_jenis = sorted(list(set(df_target['jenis'].unique()) | set(df_real['jenis'].unique())))
        jenis_options = ["Semua Jenis Pajak"] + all_jenis
        
        # Add year and tax type selection
        col_select_1, col_select_2 = st.columns(2)
        with col_select_1:
            tahun_terpilih = st.selectbox("Pilih Tahun Pajak", all_years)
        with col_select_2:
            jenis_terpilih = st.selectbox("Pilih Jenis Pajak", jenis_options)
        
        # Filter data for both charts
        df_target_filtered = df_target[df_target['tahun'] == tahun_terpilih]
        df_real_filtered = df_real[df_real['tahun'] == tahun_terpilih]

        if jenis_terpilih != "Semua Jenis Pajak":
            df_target_filtered = df_target_filtered[df_target_filtered['jenis'] == jenis_terpilih]
            df_real_filtered = df_real_filtered[df_real_filtered['jenis'] == jenis_terpilih]

        if not df_target_filtered.empty and not df_real_filtered.empty:
            
            # --- Grafik Batang (Realisasi vs Target) ---
            st.subheader("Perbandingan Target vs Realisasi")
            df_real_agg = df_real_filtered.groupby(["jenis"])["jumlah"].sum().reset_index()
            df_target_agg = df_target_filtered.groupby(["jenis"])["jumlah"].sum().reset_index()
            
            df_real_agg['tipe'] = 'Realisasi'
            df_target_agg['tipe'] = 'Target'
            
            merged_df = pd.concat([df_real_agg, df_target_agg])
            merged_df.rename(columns={'jumlah': 'Jumlah (IDR)'}, inplace=True)
            
            # Use columns to make chart more compact
            col1, col2 = st.columns([1, 4])
            with col2:
                if jenis_terpilih == "Semua Jenis Pajak":
                    chart_bar = alt.Chart(merged_df).mark_bar().encode(
                        x=alt.X("tipe", title=None),
                        y=alt.Y("Jumlah (IDR)"),
                        color="tipe",
                        column=alt.Column("jenis", header=alt.Header(titleOrient="bottom", labelOrient="bottom")),
                        tooltip=[
                            alt.Tooltip("jenis", title="Jenis Pajak"),
                            alt.Tooltip("tipe", title="Tipe Data"),
                            alt.Tooltip("Jumlah (IDR)", title="Jumlah", format=",.0f")
                        ]
                    ).properties(
                        title=f"Perbandingan Realisasi vs Target Pajak Tahun {tahun_terpilih}"
                    )
                else:
                    chart_bar = alt.Chart(merged_df).mark_bar().encode(
                        x=alt.X("tipe", title=None),
                        y=alt.Y("Jumlah (IDR)"),
                        color="tipe",
                        tooltip=[
                            alt.Tooltip("jenis", title="Jenis Pajak"),
                            alt.Tooltip("tipe", title="Tipe Data"),
                            alt.Tooltip("Jumlah (IDR)", title="Jumlah", format=",.0f")
                        ]
                    ).properties(
                        title=f"Perbandingan Realisasi vs Target Pajak {jenis_terpilih} Tahun {tahun_terpilih}"
                    )
                st.altair_chart(chart_bar, use_container_width=True)

            # --- Grafik Garis (Realisasi Bulanan) ---
            if jenis_terpilih != "Semua Jenis Pajak":
                st.write("---")
                st.subheader("Progress Realisasi Bulanan")
                # Aggregate data by month
                df_real_monthly = df_real_filtered.groupby(["bulan"])["jumlah"].sum().reset_index()
                
                # Create a mapping for month numbers to names for better readability on the chart
                month_names = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun", 7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des"}
                df_real_monthly['bulan_nama'] = df_real_monthly['bulan'].map(month_names)

                # Create the line chart
                chart_line = alt.Chart(df_real_monthly).mark_line(point=True).encode(
                    x=alt.X('bulan_nama', sort=list(month_names.values()), title='Bulan'),
                    y=alt.Y('jumlah', title='Jumlah Realisasi (IDR)'),
                    tooltip=[
                        alt.Tooltip('bulan_nama', title='Bulan'),
                        alt.Tooltip('jumlah', title='Jumlah', format=",.0f")
                    ]
                ).properties(
                    title=f"Progress Realisasi Pajak {jenis_terpilih} Tahun {tahun_terpilih}"
                ).interactive()

                st.altair_chart(chart_line, use_container_width=True)

        else:
            st.info(f"ℹ️ Belum ada data target atau realisasi untuk tahun {tahun_terpilih} dan jenis pajak {jenis_terpilih}.")
    else:
        st.info("ℹ️ Belum ada data target atau realisasi yang tersedia sama sekali.")

else:
    # --- Admin Menu (for logged-in users) ---
    st.sidebar.subheader("Menu Admin")
    admin_menu = st.sidebar.radio("Pilih Fitur", ["Dashboard", "Manajemen Akun", "Manajemen Jenis Pajak", "Manajemen Target", "Manajemen Realisasi", "Laporan", "Logout"])

    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()

    if admin_menu == "Dashboard":
        st.subheader("Dashboard Admin")
        st.info("Selamat datang di panel admin. Gunakan menu di samping untuk mengelola data pajak.")

    elif admin_menu == "Manajemen Akun":
        st.subheader("⚙️ Manajemen Akun Admin")
        st.warning("Hanya ada satu akun admin. Ubah dengan hati-hati.")
        new_username = st.text_input("Username Baru", "admin")
        new_password = st.text_input("Password Baru", type="password")
        if st.button("Ubah Akun"):
            if new_username and new_password:
                cur.execute("UPDATE admin SET username = ?, password = ? WHERE username = 'admin'", (new_username, new_password))
                conn.commit()
                st.success("✅ Akun admin berhasil diubah!")
            else:
                st.error("⚠️ Username dan password tidak boleh kosong.")

    elif admin_menu == "Manajemen Jenis Pajak":
        st.subheader("📝 Manajemen Jenis Pajak Daerah")
        jenis_pajak_df = pd.read_sql("SELECT * FROM jenis_pajak", conn)
        st.write("---")
        st.dataframe(jenis_pajak_df, use_container_width=True)
        st.write("---")

        st.subheader("Tambah Jenis Pajak")
        new_jenis = st.text_input("Nama Jenis Pajak Baru")
        if st.button("Tambah"):
            if new_jenis:
                try:
                    cur.execute("INSERT INTO jenis_pajak (jenis) VALUES (?)", (new_jenis.upper(),))
                    conn.commit()
                    st.success("✅ Jenis pajak berhasil ditambahkan!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("⚠️ Jenis pajak ini sudah ada.")
            else:
                st.error("⚠️ Nama jenis pajak tidak boleh kosong.")
        
        st.subheader("Hapus Jenis Pajak")
        jenis_to_delete = st.selectbox("Pilih Jenis Pajak untuk Dihapus", jenis_pajak_df["jenis"])
        if st.button("Hapus"):
            cur.execute("DELETE FROM jenis_pajak WHERE jenis = ?", (jenis_to_delete,))
            conn.commit()
            st.success("✅ Jenis pajak berhasil dihapus!")
            st.rerun()

    elif admin_menu == "Manajemen Target":
        st.subheader("🎯 Manajemen Target Pajak")
        jenis_list = pd.read_sql("SELECT jenis FROM jenis_pajak", conn)["jenis"].tolist()
        df_target = pd.read_sql("SELECT * FROM target", conn)
        
        # --- Tambah Target ---
        st.subheader("Tambah Data")
        with st.form("add_target_form"):
            tahun_tambah = st.number_input("Tahun", 2020, 2100, 2025, key="target_tahun_add")
            jenis_tambah = st.selectbox("Jenis Pajak", jenis_list, key="target_jenis_add")
            jumlah_str_tambah = st.text_input("Jumlah Target (Rp)", "0", help="Masukkan angka, contoh: 1000000000", key="target_jumlah_add")
            submit_tambah = st.form_submit_button("Simpan Target")
            
            if submit_tambah:
                try:
                    jumlah = float(jumlah_str_tambah.replace(".", "").replace(",", ""))
                    cur.execute("INSERT INTO target (tahun, jenis, jumlah) VALUES (?,?,?)", (tahun_tambah, jenis_tambah, jumlah))
                    conn.commit()
                    st.success(f"✅ Data target Rp {jumlah:,.0f} tersimpan!")
                    st.rerun()
                except ValueError:
                    st.error("⚠️ Input jumlah tidak valid. Masukkan hanya angka.")

        st.write("---")

        # --- Update & Hapus Target ---
        st.subheader("Update atau Hapus Data")
        if not df_target.empty:
            df_target_formatted = df_target.copy()
            df_target_formatted['jumlah'] = df_target_formatted['jumlah'].apply(lambda x: f"Rp {x:,.0f}")
            st.dataframe(df_target_formatted, use_container_width=True)

            with st.form("update_target_form"):
                target_ids = df_target['id'].tolist()
                pilih_id = st.selectbox("Pilih ID Data", target_ids, key="target_id_update")
                
                # Fetch existing data for pre-filling
                data_lama = df_target[df_target['id'] == pilih_id].iloc[0]
                tahun_update = st.number_input("Tahun Baru", 2020, 2100, int(data_lama['tahun']), key="target_tahun_update")
                jenis_update = st.selectbox("Jenis Pajak Baru", jenis_list, index=jenis_list.index(data_lama['jenis']), key="target_jenis_update")
                jumlah_update_str = st.text_input("Jumlah Baru (Rp)", f"{int(data_lama['jumlah'])}", key="target_jumlah_update")
                
                col1, col2 = st.columns(2)
                with col1:
                    submit_update = st.form_submit_button("Update Data")
                with col2:
                    submit_hapus = st.form_submit_button("Hapus Data")

                if submit_update:
                    try:
                        jumlah_update = float(jumlah_update_str.replace(".", "").replace(",", ""))
                        cur.execute("UPDATE target SET tahun=?, jenis=?, jumlah=? WHERE id=?", (tahun_update, jenis_update, jumlah_update, pilih_id))
                        conn.commit()
                        st.success(f"✅ Data ID {pilih_id} berhasil diupdate!")
                        st.rerun()
                    except ValueError:
                        st.error("⚠️ Input jumlah tidak valid. Masukkan hanya angka.")
                
                if submit_hapus:
                    cur.execute("DELETE FROM target WHERE id=?", (pilih_id,))
                    conn.commit()
                    st.success(f"✅ Data ID {pilih_id} berhasil dihapus!")
                    st.rerun()
        else:
            st.info("⚠️ Belum ada data target yang bisa diubah atau dihapus.")
        

    elif admin_menu == "Manajemen Realisasi":
        st.subheader("📈 Manajemen Realisasi Pajak")
        jenis_list = pd.read_sql("SELECT jenis FROM jenis_pajak", conn)["jenis"].tolist()
        df_real = pd.read_sql("SELECT * FROM realisasi", conn)

        # --- Tambah Realisasi ---
        st.subheader("Tambah Data")
        with st.form("add_real_form"):
            tahun_tambah = st.number_input("Tahun", 2020, 2100, 2025, key="real_tahun_add")
            bulan_tambah = st.number_input("Bulan (1-12)", 1, 12, 1, key="real_bulan_add")
            jenis_tambah = st.selectbox("Jenis Pajak", jenis_list, key="real_jenis_add")
            jumlah_str_tambah = st.text_input("Jumlah Realisasi (Rp)", "0", help="Masukkan angka, contoh: 50000000", key="real_jumlah_add")
            submit_tambah = st.form_submit_button("Simpan Realisasi")

            if submit_tambah:
                try:
                    jumlah_r = float(jumlah_str_tambah.replace(".", "").replace(",", ""))
                    cur.execute("INSERT INTO realisasi (tahun, bulan, jenis, jumlah) VALUES (?,?,?,?)", (tahun_tambah, bulan_tambah, jenis_tambah, jumlah_r))
                    conn.commit()
                    st.success(f"✅ Data realisasi Rp {jumlah_r:,.0f} tersimpan!")
                    st.rerun()
                except ValueError:
                    st.error("⚠️ Input jumlah tidak valid. Masukkan hanya angka.")

        st.write("---")

        # --- Update & Hapus Realisasi ---
        st.subheader("Update atau Hapus Data")
        if not df_real.empty:
            df_real_formatted = df_real.copy()
            df_real_formatted['jumlah'] = df_real_formatted['jumlah'].apply(lambda x: f"Rp {x:,.0f}")
            st.dataframe(df_real_formatted, use_container_width=True)

            with st.form("update_real_form"):
                real_ids = df_real['id'].tolist()
                pilih_id = st.selectbox("Pilih ID Data", real_ids, key="real_id_update")
                
                # Fetch existing data for pre-filling
                data_lama = df_real[df_real['id'] == pilih_id].iloc[0]
                tahun_update = st.number_input("Tahun Baru", 2020, 2100, int(data_lama['tahun']), key="real_tahun_update")
                bulan_update = st.number_input("Bulan Baru (1-12)", 1, 12, int(data_lama['bulan']), key="real_bulan_update")
                jenis_update = st.selectbox("Jenis Pajak Baru", jenis_list, index=jenis_list.index(data_lama['jenis']), key="real_jenis_update")
                jumlah_update_str = st.text_input("Jumlah Baru (Rp)", f"{int(data_lama['jumlah'])}", key="real_jumlah_update")
                
                col1, col2 = st.columns(2)
                with col1:
                    submit_update = st.form_submit_button("Update Data")
                with col2:
                    submit_hapus = st.form_submit_button("Hapus Data")

                if submit_update:
                    try:
                        jumlah_update = float(jumlah_update_str.replace(".", "").replace(",", ""))
                        cur.execute("UPDATE realisasi SET tahun=?, bulan=?, jenis=?, jumlah=? WHERE id=?", (tahun_update, bulan_update, jenis_update, jumlah_update, pilih_id))
                        conn.commit()
                        st.success(f"✅ Data ID {pilih_id} berhasil diupdate!")
                        st.rerun()
                    except ValueError:
                        st.error("⚠️ Input jumlah tidak valid. Masukkan hanya angka.")
                
                if submit_hapus:
                    cur.execute("DELETE FROM realisasi WHERE id=?", (pilih_id,))
                    conn.commit()
                    st.success(f"✅ Data ID {pilih_id} berhasil dihapus!")
                    st.rerun()
        else:
            st.info("⚠️ Belum ada data realisasi yang bisa diubah atau dihapus.")
        

    elif admin_menu == "Laporan":
        st.subheader("📄 Laporan Pajak Daerah")
        df_target = pd.read_sql("SELECT tahun, jenis, jumlah FROM target", conn)
        df_real = pd.read_sql("SELECT tahun, jenis, SUM(jumlah) AS jumlah FROM realisasi GROUP BY tahun, jenis", conn)

        if not df_target.empty and not df_real.empty:
            merged_df = pd.merge(df_target, df_real, on=['tahun', 'jenis'], how='left', suffixes=('_target', '_realisasi')).fillna(0)
            merged_df['persentase'] = (merged_df['jumlah_realisasi'] / merged_df['jumlah_target']) * 100
            
            merged_df['jumlah_target'] = merged_df['jumlah_target'].apply(lambda x: f"Rp {x:,.0f}")
            merged_df['jumlah_realisasi'] = merged_df['jumlah_realisasi'].apply(lambda x: f"Rp {x:,.0f}")
            merged_df['persentase'] = merged_df['persentase'].apply(lambda x: f"{x:.2f}%")
            
            merged_df = merged_df.rename(columns={
                "jumlah_target": "Target (Rp)",
                "jumlah_realisasi": "Realisasi (Rp)",
                "persentase": "Pencapaian (%)"
            })
            
            st.dataframe(merged_df, use_container_width=True)
            
            csv_data = merged_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Unduh Laporan CSV",
                data=csv_data,
                file_name="laporan_pajak.csv",
                mime="text/csv"
            )
        else:
            st.warning("⚠️ Data belum lengkap untuk membuat laporan.")