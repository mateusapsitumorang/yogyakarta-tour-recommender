import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from config import KABUPATEN, KATEGORI_WISATA, HARGA_PENGINAPAN
from path_ranking import PathRankingAlgorithm

class RecommendationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistem Rekomendasi Paket Wisata Yogyakarta")
        self.root.geometry("800x600")
        
        # Label judul
        self.title_label = tk.Label(
            root, 
            text="Sistem Rekomendasi Paket Wisata Yogyakarta", 
            font=("Arial", 16, "bold")
        )
        self.title_label.pack(pady=20)
        
        # Frame untuk form kriteria
        self.criteria_frame = ttk.LabelFrame(root, text="Kriteria Pencarian")
        self.criteria_frame.pack(padx=20, pady=10, fill="x")
        
        # Grid untuk form
        self.setup_criteria_form()
        
        # Tombol cari rekomendasi
        self.search_button = ttk.Button(
            root,
            text="Cari Rekomendasi",
            command=self.search_recommendations
        )
        self.search_button.pack(pady=10)
        
        # Frame untuk hasil rekomendasi
        self.results_frame = ttk.LabelFrame(root, text="Hasil Rekomendasi")
        self.results_frame.pack(padx=20, pady=10, fill="both", expand=True)
        
        # Notebook untuk hasil rekomendasi
        self.results_notebook = ttk.Notebook(self.results_frame)
        self.results_notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Tombol ekspor hasil
        self.export_button = ttk.Button(
            root,
            text="Ekspor Hasil (CSV)",
            command=self.export_results,
            state=tk.DISABLED
        )
        self.export_button.pack(pady=10)
        
        # Variabel untuk menyimpan hasil rekomendasi
        self.recommendations = []
    
    def setup_criteria_form(self):
        """Siapkan form untuk input kriteria"""
        # Buat grid di dalam criteria_frame
        for i in range(6):
            self.criteria_frame.columnconfigure(i, weight=1)
        
        # Kabupaten
        ttk.Label(self.criteria_frame, text="Kabupaten:").grid(
            row=0, column=0, padx=5, pady=5, sticky=tk.W
        )
        self.kabupaten_var = tk.StringVar()
        self.kabupaten_combo = ttk.Combobox(
            self.criteria_frame,
            textvariable=self.kabupaten_var,
            values=["Semua"] + KABUPATEN,
            state="readonly"
        )
        self.kabupaten_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        self.kabupaten_combo.current(0)
        
        # Kategori Wisata
        ttk.Label(self.criteria_frame, text="Kategori Wisata:").grid(
            row=0, column=2, padx=5, pady=5, sticky=tk.W
        )
        self.kategori_var = tk.StringVar()
        self.kategori_combo = ttk.Combobox(
            self.criteria_frame,
            textvariable=self.kategori_var,
            values=["Semua"] + KATEGORI_WISATA,
            state="readonly"
        )
        self.kategori_combo.grid(row=0, column=3, padx=5, pady=5, sticky=tk.W)
        self.kategori_combo.current(0)
        
        # Minimum Rating Tempat Wisata
        ttk.Label(self.criteria_frame, text="Min. Rating Wisata:").grid(
            row=1, column=0, padx=5, pady=5, sticky=tk.W
        )
        self.min_rating_wisata_var = tk.DoubleVar(value=3.0)
        self.min_rating_wisata_scale = ttk.Scale(
            self.criteria_frame,
            from_=1.0,
            to=5.0,
            orient=tk.HORIZONTAL,
            variable=self.min_rating_wisata_var,
            length=100
        )
        self.min_rating_wisata_scale.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(
            self.criteria_frame, 
            textvariable=self.min_rating_wisata_var
        ).grid(row=1, column=1, padx=(110, 0), pady=5, sticky=tk.W)
        
        # Maximum Harga Penginapan
        ttk.Label(self.criteria_frame, text="Rentang Harga Penginapan:").grid(
            row=1, column=2, padx=5, pady=5, sticky=tk.W
        )
        self.max_harga_var = tk.StringVar()
        self.max_harga_combo = ttk.Combobox(
            self.criteria_frame,
            textvariable=self.max_harga_var,
            values=list(HARGA_PENGINAPAN.keys()),
            state="readonly"
        )
        self.max_harga_combo.grid(row=1, column=3, padx=5, pady=5, sticky=tk.W)
        self.max_harga_combo.current(2)  # Default: Mahal
        
        # Minimum Rating Penginapan
        ttk.Label(self.criteria_frame, text="Min. Rating Penginapan:").grid(
            row=2, column=0, padx=5, pady=5, sticky=tk.W
        )
        self.min_rating_penginapan_var = tk.DoubleVar(value=3.0)
        self.min_rating_penginapan_scale = ttk.Scale(
            self.criteria_frame,
            from_=1.0,
            to=5.0,
            orient=tk.HORIZONTAL,
            variable=self.min_rating_penginapan_var,
            length=100
        )
        self.min_rating_penginapan_scale.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(
            self.criteria_frame, 
            textvariable=self.min_rating_penginapan_var
        ).grid(row=2, column=1, padx=(110, 0), pady=5, sticky=tk.W)
        
        # Minimum Rating Rumah Makan
        ttk.Label(self.criteria_frame, text="Min. Rating Rumah Makan:").grid(
            row=2, column=2, padx=5, pady=5, sticky=tk.W
        )
        self.min_rating_rm_var = tk.DoubleVar(value=3.0)
        self.min_rating_rm_scale = ttk.Scale(
            self.criteria_frame,
            from_=1.0,
            to=5.0,
            orient=tk.HORIZONTAL,
            variable=self.min_rating_rm_var,
            length=100
        )
        self.min_rating_rm_scale.grid(row=2, column=3, padx=5, pady=5, sticky=tk.W)
        ttk.Label(
            self.criteria_frame, 
            textvariable=self.min_rating_rm_var
        ).grid(row=2, column=3, padx=(110, 0), pady=5, sticky=tk.W)
    
    def get_criteria(self):
        """Ambil kriteria dari form"""
        kabupaten = self.kabupaten_var.get()
        kabupaten = None if kabupaten == "Semua" else kabupaten
        
        kategori = self.kategori_var.get()
        kategori = None if kategori == "Semua" else kategori
        
        min_rating_wisata = self.min_rating_wisata_var.get()
        
        harga_kategori = self.max_harga_var.get()
        if harga_kategori == "Murah":
            max_harga = 300000
        elif harga_kategori == "Sedang":
            max_harga = 700000
        else:  # Mahal
            max_harga = 1500000
        
        min_rating_penginapan = self.min_rating_penginapan_var.get()
        min_rating_rm = self.min_rating_rm_var.get()
        
        return {
            'kabupaten': kabupaten,
            'kategori_wisata': kategori,
            'min_rating_tempat_wisata': min_rating_wisata,
            'max_harga_penginapan': max_harga,
            'min_rating_penginapan': min_rating_penginapan,
            'min_rating_rumah_makan': min_rating_rm
        }
    
    def clear_results(self):
        """Hapus semua tab hasil"""
        for tab in self.results_notebook.tabs():
            self.results_notebook.forget(tab)
    
    def display_recommendation(self, rec, index):
        """Tampilkan rekomendasi dalam tab"""
        tab = ttk.Frame(self.results_notebook)
        self.results_notebook.add(tab, text=f"Rekomendasi #{index+1}")
        
        # Buat frame dengan padding
        content_frame = ttk.Frame(tab, padding=10)
        content_frame.pack(fill="both", expand=True)
        
        # Skor rekomendasi
        ttk.Label(
            content_frame,
            text=f"Skor: {rec['total_score']:.4f}",
            font=("Arial", 10, "italic")
        ).pack(anchor="e", pady=(0, 10))
        
        # Penginapan
        penginapan_frame = ttk.LabelFrame(content_frame, text="Penginapan")
        penginapan_frame.pack(fill="x", pady=5)
        
        penginapan = rec['penginapan']
        ttk.Label(
            penginapan_frame,
            text=penginapan['nama'],
            font=("Arial", 12, "bold")
        ).pack(anchor="w", padx=5, pady=2)
        
        ttk.Label(
            penginapan_frame,
            text=f"Rating: {penginapan['rating']}/5.0"
        ).pack(anchor="w", padx=5, pady=2)
        
        ttk.Label(
            penginapan_frame,
            text=f"Harga: Rp{penginapan['harga']:,}"
        ).pack(anchor="w", padx=5, pady=2)
        
        # Tempat Wisata 1
        tw1_frame = ttk.LabelFrame(content_frame, text="Tempat Wisata 1")
        tw1_frame.pack(fill="x", pady=5)
        
        tw1 = rec['tempat_wisata_1']
        ttk.Label(
            tw1_frame,
            text=tw1['nama'],
            font=("Arial", 12, "bold")
        ).pack(anchor="w", padx=5, pady=2)
        
        ttk.Label(
            tw1_frame,
            text=f"Kategori: {tw1['kategori']}"
        ).pack(anchor="w", padx=5, pady=2)
        
        ttk.Label(
            tw1_frame,
            text=f"Rating: {tw1['rating']}/5.0"
        ).pack(anchor="w", padx=5, pady=2)
        
        # Tempat Wisata 2
        tw2_frame = ttk.LabelFrame(content_frame, text="Tempat Wisata 2")
        tw2_frame.pack(fill="x", pady=5)
        
        tw2 = rec['tempat_wisata_2']
        ttk.Label(
            tw2_frame,
            text=tw2['nama'],
            font=("Arial", 12, "bold")
        ).pack(anchor="w", padx=5, pady=2)
        
        ttk.Label(
            tw2_frame,
            text=f"Kategori: {tw2['kategori']}"
        ).pack(anchor="w", padx=5, pady=2)
        
        ttk.Label(
            tw2_frame,
            text=f"Rating: {tw2['rating']}/5.0"
        ).pack(anchor="w", padx=5, pady=2)
        
        # Rumah Makan
        rm_frame = ttk.LabelFrame(content_frame, text="Rumah Makan")
        rm_frame.pack(fill="x", pady=5)
        
        rm = rec['rumah_makan']
        ttk.Label(
            rm_frame,
            text=rm['nama'],
            font=("Arial", 12, "bold")
        ).pack(anchor="w", padx=5, pady=2)
        
        ttk.Label(
            rm_frame,
            text=f"Rating: {rm['rating']}/5.0"
        ).pack(anchor="w", padx=5, pady=2)
    
    def search_recommendations(self):
        """Cari rekomendasi berdasarkan kriteria"""
        self.search_button.config(text="Mencari...", state=tk.DISABLED)
        self.root.update()
        
        try:
            criteria = self.get_criteria()
            
            pra = PathRankingAlgorithm("bolt://localhost:7687", "neo4j", "puan061002")
            self.recommendations = pra.get_recommendations(criteria)
            pra.close()
            
            self.clear_results()
            
            if not self.recommendations:
                messagebox.showinfo("Tidak Ada Hasil", "Tidak ada rekomendasi yang sesuai dengan kriteria yang dipilih.")
                self.export_button.config(state=tk.DISABLED)
            else:
                for i, rec in enumerate(self.recommendations):
                    self.display_recommendation(rec, i)
                self.export_button.config(state=tk.NORMAL)
        
        except Exception as e:
            messagebox.showerror("Error", f"Terjadi kesalahan: {str(e)}")
        
        self.search_button.config(text="Cari Rekomendasi", state=tk.NORMAL)
    
    def export_results(self):
        if not self.recommendations:
            messagebox.showinfo("Info", "Tidak ada hasil untuk diekspor.")
            return
        
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")], title="Simpan Hasil Rekomendasi")
        
        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['no', 'skor', 'nama_penginapan', 'rating_penginapan', 'harga_penginapan', 'nama_tempat_wisata_1', 'kategori_tempat_wisata_1', 'rating_tempat_wisata_1', 'nama_tempat_wisata_2', 'kategori_tempat_wisata_2', 'rating_tempat_wisata_2', 'nama_rumah_makan', 'rating_rumah_makan']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    for i, rec in enumerate(self.recommendations, 1):
                        writer.writerow({
                            'no': i,
                            'skor': rec['total_score'],
                            'nama_penginapan': rec['penginapan']['nama'],
                            'rating_penginapan': rec['penginapan']['rating'],
                            'harga_penginapan': rec['penginapan']['harga'],
                            'nama_tempat_wisata_1': rec['tempat_wisata_1']['nama'],
                            'kategori_tempat_wisata_1': rec['tempat_wisata_1']['kategori'],
                            'rating_tempat_wisata_1': rec['tempat_wisata_1']['rating'],
                            'nama_tempat_wisata_2': rec['tempat_wisata_2']['nama'],
                            'kategori_tempat_wisata_2': rec['tempat_wisata_2']['kategori'],
                            'rating_tempat_wisata_2': rec['tempat_wisata_2']['rating'],
                            'nama_rumah_makan': rec['rumah_makan']['nama'],
                            'rating_rumah_makan': rec['rumah_makan']['rating']
                        })
                messagebox.showinfo("Ekspor Berhasil", f"Hasil rekomendasi telah disimpan ke:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error Ekspor", f"Gagal mengekspor hasil: {str(e)}")

def main():
    root = tk.Tk()
    app = RecommendationApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
