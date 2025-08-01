"""
Code untuk menghitung dan mengevaluasi metrik kepuasan pengguna berdasarkan rekomendasi dan feedback.
Modul ini menyediakan fungsi untuk menghitung metrik seperti precision, recall, NDCG, dan hit rate,
serta memformat hasil evaluasi dalam format HTML dan CSV.
"""
import json
import csv
import tempfile
import numpy as np
from collections import defaultdict
from flask import current_app
from models import UserCriteria, Recommendation, UserRecommendationFeedback

DEFAULT_K = [3, 5, 7]

def format_value(v, decimals=2, as_percent=False):
    """
    Mengformat nilai numerik menjadi string dengan jumlah desimal tertentu atau dalam bentuk persentase.

    Args:
        v (float): Nilai numerik yang akan diformat.
        decimals (int): Jumlah digit desimal (default: 2).
        as_percent (bool): Jika True, nilai dikonversi ke persentase (default: False).

    Returns:
        str: Nilai yang telah diformat sebagai string.
    """
    if as_percent:
        return f"{v * 100:.{decimals}f}%"
    return f"{v:.{decimals}f}"

def calculate_metrics_feedback(
    recommendations,
    feedback_list,
    k_values=DEFAULT_K,
    feedback_mode='all', 
    logger=None
):
    """
    Menghitung metrik evaluasi (precision, recall, NDCG, hit rate) berdasarkan rekomendasi dan feedback pengguna.

    Fungsi ini mengelompokkan feedback berdasarkan kriteria, menghitung metrik untuk setiap nilai k,
    dan menyediakan ringkasan hasil evaluasi.

    Args:
        recommendations (list): Daftar objek rekomendasi.
        feedback_list (list): Daftar objek feedback pengguna.
        k_values (list): Daftar nilai k untuk evaluasi top-k (default: [3, 5, 7]).
        feedback_mode (str): Mode feedback ('all', 'like', atau 'dislike') (default: 'all').
        logger (Logger): Objek logger untuk mencatat informasi (default: logger dari aplikasi Flask).

    Returns:
        dict: Dictionary berisi metrik evaluasi untuk setiap k dan ringkasan hasil.
    """
    if logger is None:
        logger = current_app.logger

    fbs_by_crit = defaultdict(list)
    for fb in feedback_list:
        if fb.feedback_type == 'reset':
            continue
        fbs_by_crit[fb.criteria_id].append(fb)

    temp = {k: {'precision': [], 'recall': [], 'ndcg': [], 'hit_rate': []} for k in k_values}
    processed_users = set()
    total_feedback = 0
    total_likes = 0
    total_dislikes = 0

    for crit_id, fbs in fbs_by_crit.items():
        crit_recs = [r for r in recommendations if r.criteria_id == crit_id]
        if not crit_recs:
            continue

        # Menentukan item relevan berdasarkan feedback 'like'
        relevant = {fb.package_id for fb in fbs if fb.feedback_type == 'like'}
        total_pos = len(relevant)
        if total_pos == 0:
            continue

        # Menghitung jumlah like dan dislike per kriteria
        likes = sum(1 for fb in fbs if fb.feedback_type == 'like')
        dislikes = sum(1 for fb in fbs if fb.feedback_type == 'dislike')
        total_likes += likes
        total_dislikes += dislikes

        processed_users.update({fb.user_id for fb in fbs})
        total_feedback += len(fbs)

        sorted_recs = sorted(crit_recs, key=lambda r: (r.skor or 0), reverse=True)

        for k in k_values:
            topk = sorted_recs[:k]
            # Menghitung true positives (tp) dan false positives (fp)
            if feedback_mode == 'like':
                tp = sum(1 for r in topk if r.package_id in relevant)
                fp = sum(1 for r in topk if r.package_id not in relevant)
            elif feedback_mode == 'dislike':
                # Untuk mode dislike, relevan adalah item dengan feedback 'dislike'
                relevant_dislike = {fb.package_id for fb in fbs if fb.feedback_type == 'dislike'}
                tp = sum(1 for r in topk if r.package_id in relevant_dislike)
                fp = sum(1 for r in topk if r.package_id not in relevant_dislike)
            else:  # all
                tp = sum(1 for r in topk if r.package_id in relevant)
                # Item tanpa feedback 'like' dianggap tidak relevan
                fp = sum(1 for r in topk if r.package_id not in relevant)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / total_pos if total_pos > 0 else 0.0

            dcg = sum((1 if r.package_id in relevant else 0) / np.log2(i + 2) for i, r in enumerate(topk))
            idcg = sum(1.0 / np.log2(i + 2) for i in range(min(total_pos, k)))
            ndcg = dcg / idcg if idcg > 0 else 0.0

            hit = 1 if tp > 0 else 0

            temp[k]['precision'].append(precision)
            temp[k]['recall'].append(recall)
            temp[k]['ndcg'].append(ndcg)
            temp[k]['hit_rate'].append(hit)

        logger.info(f"[USER] Crit {crit_id}: relevant={len(relevant)}, total_feedback={len(fbs)}, likes={likes}, dislikes={dislikes}")

    final = {}
    for k in k_values:
        arrp = temp[k]['precision']
        arrr = temp[k]['recall']
        arrn = temp[k]['ndcg']
        arrh = temp[k]['hit_rate']
        final[k] = {
            'precision': {'mean': float(np.mean(arrp)) if arrp else 0.0},
            'recall': {'mean': float(np.mean(arrr)) if arrr else 0.0},
            'ndcg': {'mean': float(np.mean(arrn)) if arrn else 0.0},
            'hit_rate': {'mean': float(np.mean(arrh)) if arrh else 0.0},
        }

    summary = {
        'precision': final[k_values[0]]['precision']['mean'] if k_values else 0.0,
        'recall': final[k_values[0]]['recall']['mean'] if k_values else 0.0,
        'ndcg': final[k_values[0]]['ndcg']['mean'] if k_values else 0.0,
        'hit_rate': final[k_values[0]]['hit_rate']['mean'] if k_values else 0.0,
        'processed_users': len(processed_users),
        'processed_criteria': len(fbs_by_crit),
        'total_feedback': total_feedback,
        'total_likes': total_likes,
        'total_dislikes': total_dislikes
    }

    return {'results': final, 'summary': summary}

def evaluate_user_satisfaction(user_criteria, recs, feedback_list, k_values=DEFAULT_K, feedback_mode='all', logger=None):
    """
    Mengevaluasi kepuasan pengguna berdasarkan kriteria, rekomendasi, dan feedback.

    Fungsi ini memanggil calculate_metrics_feedback untuk menghitung metrik evaluasi.

    Args:
        user_criteria (list): Daftar objek kriteria pengguna.
        recs (list): Daftar objek rekomendasi.
        feedback_list (list): Daftar objek feedback pengguna.
        k_values (list): Daftar nilai k untuk evaluasi top-k (default: [3, 5, 7]).
        feedback_mode (str): Mode feedback ('all', 'like', atau 'dislike') (default: 'all').
        logger (Logger): Objek logger untuk mencatat informasi (default: None).

    Returns:
        dict: Dictionary berisi metrik evaluasi dan ringkasan hasil.
    """
    return calculate_metrics_feedback(recs, feedback_list, k_values, feedback_mode, logger)

def format_evaluation_results_html(results, k_values=DEFAULT_K, decimals=2, percent=False):
    """
    Memformat hasil evaluasi menjadi tabel HTML untuk ditampilkan.

    Fungsi ini menghasilkan tabel HTML yang berisi metrik evaluasi (precision, recall, NDCG, hit rate)
    untuk setiap nilai k, serta ringkasan statistik.

    Args:
        results (dict): Hasil evaluasi dari fungsi calculate_metrics_feedback.
        k_values (list): Daftar nilai k untuk evaluasi top-k (default: [3, 5, 7]).
        decimals (int): Jumlah digit desimal untuk format nilai (default: 2).
        percent (bool): Jika True, nilai ditampilkan sebagai persentase (default: False).

    Returns:
        str: String HTML yang berisi tabel dan ringkasan evaluasi.
    """
    th_cols = ''.join(f'<th>K={k}{" (%)" if percent else ""}</th>' for k in k_values)
    html = [
        '<table>',
        '<thead><tr><th>Metrik</th>' + th_cols + '</tr></thead>',
        '<tbody>'
    ]
    metrics = [
        ('Precision@k', 'precision'),
        ('Recall@k', 'recall'),
        ('NDCG@k', 'ndcg'),
        ('Hit Rate@k', 'hit_rate'),
    ]

    for label, key in metrics:
        row = [f'<tr><td>{label}</td>']
        for k in k_values:
            mean = results['results'].get(k, {}).get(key, {}).get('mean', 0.0)
            row.append(f'<td>{format_value(mean, decimals, percent)}</td>')
        row.append('</tr>')
        html.append(''.join(row))

    html.append('</tbody></table><ul>')
    summary_items = [
        ('processed_users', 'Processed Users'),
        ('processed_criteria', 'Processed Criteria'),
        ('total_feedback', 'Total Feedback'),
        ('total_likes', 'Total Likes'),
        ('total_dislikes', 'Total Dislikes')
    ]
    
    for key, label in summary_items:
        val = results['summary'].get(key, 0)
        html.append(f'<li>{label}: {val}</li>')
        if key == 'total_dislikes':  
            html.append('<br>')
    html.append('</ul>')
    return ''.join(html)

def export_all_evaluations_to_csv(user_id, criteria_id=None, k_values=DEFAULT_K, feedback_mode='all', logger=None):
    """
    Mengekspor hasil evaluasi ke file CSV untuk pengguna tertentu.

    Fungsi ini mengambil data kriteria, rekomendasi, dan feedback untuk pengguna tertentu,
    menghitung metrik evaluasi, dan mengekspor hasilnya ke file CSV sementara.

    Args:
        user_id (int): ID pengguna yang dievaluasi.
        criteria_id (int, optional): ID kriteria tertentu (jika None, semua kriteria diambil).
        k_values (list): Daftar nilai k untuk evaluasi top-k (default: [3, 5, 7]).
        feedback_mode (str): Mode feedback ('all', 'like', atau 'dislike') (default: 'all').
        logger (Logger): Objek logger untuk mencatat informasi (default: None).

    Returns:
        tuple: (str, str) berisi nama file CSV sementara dan pesan error (jika ada).
    """
    if criteria_id:
        user_criteria = UserCriteria.query.filter_by(id_user=user_id, id_kriteria=criteria_id).all()
        recs = Recommendation.query.filter_by(user_id=user_id, criteria_id=criteria_id).all()
    else:
        user_criteria = UserCriteria.query.filter_by(id_user=user_id).all()
        recs = Recommendation.query.filter_by(user_id=user_id).all()

    rec_ids = [r.id for r in recs]
    feedback_list = []
    if rec_ids:
        feedback_list = UserRecommendationFeedback.query.filter(
            UserRecommendationFeedback.user_id == user_id,
            UserRecommendationFeedback.recommendation_id.in_(rec_ids)
        ).all()
        for fb in feedback_list:
            fb.criteria_id = fb.recommendation.criteria_id
            fb.package_id = fb.recommendation.package_id

    if not user_criteria or len([fb for fb in feedback_list if fb.feedback_type != 'reset']) < 2:
        return None, "Minimal 1 kriteria dan 2 feedback diperlukan"

    tf = tempfile.NamedTemporaryFile(mode='w', delete=False, newline='', encoding='utf-8')
    fieldnames = ['Evaluation Type', 'Metric'] + [f'K={k}_Mean' for k in k_values]
    writer = csv.DictWriter(tf, fieldnames=fieldnames)
    writer.writeheader()

    metrics = [
        ('Precision@k', 'precision'),
        ('Recall@k', 'recall'),
        ('NDCG@k', 'ndcg'),
        ('Hit Rate@k', 'hit_rate'),
    ]

    res = evaluate_user_satisfaction(user_criteria, recs, feedback_list, k_values, feedback_mode, logger)
    for m_label, key in metrics:
        row = {'Evaluation Type': f'User Satisfaction ({feedback_mode})', 'Metric': m_label}
        for k in k_values:
            val = res['results'][k][key]['mean']
            row[f'K={k}_Mean'] = f"{val:.4f}"
        writer.writerow(row)
    tf.write('\n')

    summary_rows = [
        ('Summary', 'Processed Users', res['summary']['processed_users']),
        ('Summary', 'Processed Criteria', res['summary']['processed_criteria']),
        ('Summary', 'Total Feedback', res['summary']['total_feedback']),
    ]
    for etype, metric, val in summary_rows:
        writer.writerow({
            'Evaluation Type': etype,
            'Metric': metric,
            'K=3_Mean': val
        })

    tf.close()
    return tf.name, None