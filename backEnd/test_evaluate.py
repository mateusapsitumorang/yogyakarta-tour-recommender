from typing import List, Dict, Set, Tuple
from collections import defaultdict
import numpy as np
import math

def evaluate_real_data_debug(get_recommendations_func, user_criteria_list, feedback_list, k_values=[3, 5, 7]):
    """
    Versi debug dari fungsi evaluasi untuk mengidentifikasi masalah
    """
    print("=== DEBUG: Starting evaluation ===")
    print(f"Total user criteria: {len(user_criteria_list)}")
    print(f"Total feedback: {len(feedback_list)}")
    
    # Dictionary untuk menyimpan hasil evaluasi per user
    user_evaluations = {}

    # Grup feedback berdasarkan user_id
    user_feedback_map = defaultdict(list)
    for feedback in feedback_list:
        user_feedback_map[feedback.user_id].append(feedback)

    print(f"\n=== DEBUG: Feedback Distribution ===")
    for user_id, feedbacks in user_feedback_map.items():
        likes = [fb.package_id for fb in feedbacks if fb.feedback_type == 'like']
        dislikes = [fb.package_id for fb in feedbacks if fb.feedback_type != 'like']
        print(f"User {user_id}: {len(likes)} likes, {len(dislikes)} dislikes")
        print(f"  Liked packages: {likes[:5]}{'...' if len(likes) > 5 else ''}")

    # Proses setiap user criteria
    processed_users = 0
    
    for criteria in user_criteria_list:
        user_id = criteria.id_user
        print(f"\n=== DEBUG: Processing User {user_id} ===")

        # Ambil feedback untuk user ini
        user_feedbacks = user_feedback_map.get(user_id, [])
        print(f"User {user_id} has {len(user_feedbacks)} feedback entries")

        # Identifikasi item yang disukai (feedback positif)
        liked_items = {fb.package_id for fb in user_feedbacks if fb.feedback_type == 'like'}
        print(f"User {user_id} liked items: {list(liked_items)}")

        # Skip jika tidak ada feedback positif
        if not liked_items:
            print(f"User {user_id} has no liked items, skipping...")
            continue

        # Buat criteria dictionary untuk sistem rekomendasi
        criteria_dict = {
            'kabupaten': criteria.kabupaten.split(', ') if criteria.kabupaten else [],
            'kategori_wisata': criteria.kategori_wisata,
            'min_rating_tempat_wisata': criteria.rating_tempat_wisata or 3.0,
            'min_rating_penginapan': criteria.rating_penginapan or 3.0,
            'min_rating_rumah_makan': criteria.rating_rumah_makan or 3.0,
            'min_harga_penginapan': 0,
            'max_harga_penginapan': criteria.harga_penginapan or 1500000,
            'use_reviews': criteria.metode_pencarian == 'Rating dan Ulasan',
            'num_recommendations': max(k_values),
        }
        
        print(f"Criteria for user {user_id}: {criteria_dict}")

        try:
            # Dapatkan rekomendasi dari sistem
            recommendations = get_recommendations_func(criteria_dict)
            if not recommendations:
                print(f"No recommendations returned for user {user_id}")
                continue

            print(f"User {user_id} got {len(recommendations)} recommendations")

            # Extract package IDs dari rekomendasi
            recommended_packages = [rec.get('recommendationId') for rec in recommendations]
            print(f"Recommended package IDs: {recommended_packages}")

            # DEBUG: Cek overlap antara rekomendasi dan liked items
            overlap = set(recommended_packages) & liked_items
            print(f"Overlap between recommendations and liked items: {list(overlap)}")
            print(f"Overlap count: {len(overlap)} out of {len(recommended_packages)} recommendations")

            # DEBUG: Cek apakah ada None dalam recommended_packages
            none_count = recommended_packages.count(None)
            if none_count > 0:
                print(f"WARNING: {none_count} recommendations have None as ID")
                # Filter out None values
                recommended_packages = [pkg_id for pkg_id in recommended_packages if pkg_id is not None]
                print(f"After filtering None: {recommended_packages}")

            # Evaluasi untuk user ini
            user_evaluations[user_id] = {
                'relevant_items': liked_items,
                'recommendations': recommended_packages,
            }

            processed_users += 1

        except Exception as e:
            print(f"Error processing user {user_id}: {str(e)}")
            import traceback
            traceback.print_exc()
            continue

    print(f"\n=== DEBUG: Summary ===")
    print(f"Processed users: {processed_users}")
    print(f"User evaluations: {len(user_evaluations)}")

    # Jika tidak ada data yang bisa diproses
    if processed_users == 0:
        return {
            'error': 'Tidak ada data yang cukup untuk evaluasi. Pastikan ada user dengan feedback positif.',
            'processed_users': 0,
            'total_criteria': len(user_criteria_list),
            'total_feedback': len(feedback_list),
        }

    # DEBUG: Analisis detail per user sebelum menghitung metrik
    print(f"\n=== DEBUG: Detailed User Analysis ===")
    for user_id, data in user_evaluations.items():
        relevant_items = data['relevant_items']
        recommendations = data['recommendations']
        overlap = set(recommendations) & relevant_items
        
        print(f"User {user_id}:")
        print(f"  Relevant items ({len(relevant_items)}): {list(relevant_items)[:10]}{'...' if len(relevant_items) > 10 else ''}")
        print(f"  Recommendations ({len(recommendations)}): {recommendations}")
        print(f"  Overlap ({len(overlap)}): {list(overlap)}")
        print(f"  Precision would be: {len(overlap) / len(recommendations) if recommendations else 0:.4f}")

    # Hitung metrik evaluasi untuk semua user
    evaluation_results = {}

    # Menghitung untuk setiap k
    for k in k_values:
        print(f"\n=== DEBUG: Calculating metrics for k={k} ===")
        precision_scores = []
        recall_scores = []
        ndcg_scores = []
        hit_rate_scores = []

        for user_id, data in user_evaluations.items():
            relevant_items = data['relevant_items']
            recommendations = data['recommendations'][:k]  # Ambil top-k

            print(f"User {user_id} (k={k}):")
            print(f"  Relevant: {len(relevant_items)} items")
            print(f"  Recommendations: {len(recommendations)} items")

            # Check if we have any recommendations before calculating precision and recall
            if len(recommendations) == 0:
                print(f"  No recommendations for user {user_id}. Skipping calculation.")
                continue
            
            # Precision@k
            relevant_count = len(set(recommendations) & relevant_items)
            precision = relevant_count / len(recommendations)
            precision_scores.append(precision)
            print(f"  Precision@{k}: {precision:.4f} ({relevant_count}/{len(recommendations)})")

            # Recall@k  
            recall = relevant_count / len(relevant_items) if relevant_items else 0.0
            recall_scores.append(recall)
            print(f"  Recall@{k}: {recall:.4f} ({relevant_count}/{len(relevant_items)})")

            # Hit Rate@k
            hit_rate = 1.0 if any(item in relevant_items for item in recommendations) else 0.0
            hit_rate_scores.append(hit_rate)
            print(f"  Hit Rate@{k}: {hit_rate:.4f}")

            # NDCG@k (simplified binary relevance)
            dcg = sum(1.0 / math.log2(i + 1) for i, item in enumerate(recommendations, 1) if item in relevant_items)
            idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(k, len(relevant_items)) + 1))
            ndcg = dcg / idcg if idcg > 0 else 0.0
            ndcg_scores.append(ndcg)
            print(f"  NDCG@{k}: {ndcg:.4f}")

        print(f"Summary for k={k}:")
        print(f"  Precision scores: {precision_scores}")
        print(f"  Mean precision: {np.mean(precision_scores):.4f}")

        # Simpan hasil rata-rata untuk k ini
        evaluation_results[k] = {
            'precision': {
                'mean': np.mean(precision_scores),
                'std': np.std(precision_scores),
                'values': precision_scores
            },
            'recall': {
                'mean': np.mean(recall_scores),
                'std': np.std(recall_scores),
                'values': recall_scores
            },
            'ndcg': {
                'mean': np.mean(ndcg_scores),
                'std': np.std(ndcg_scores),
                'values': ndcg_scores
            },
            'hit_rate': {
                'mean': np.mean(hit_rate_scores),
                'std': np.std(hit_rate_scores),
                'values': hit_rate_scores
            }
        }

    # Tambahkan informasi summary
    evaluation_results['summary'] = {
        'processed_users': processed_users,
        'total_criteria': len(user_criteria_list),
        'total_feedback': len(feedback_list),
        'avg_relevant_items_per_user': np.mean([len(data['relevant_items']) for data in user_evaluations.values()]),
        'avg_recommendations_per_user': np.mean([len(data['recommendations']) for data in user_evaluations.values()])
    }
    
    print(f"\n=== DEBUG: Final Results ===")
    print("Final Evaluation Results:", evaluation_results)

    return evaluation_results


def diagnose_recommendation_system(get_recommendations_func, user_criteria_list, feedback_list):
    """
    Fungsi khusus untuk mendiagnosis masalah sistem rekomendasi
    """
    print("=== DIAGNOSIS: Recommendation System Issues ===")
    
    # 1. Cek struktur data
    print(f"1. Data Structure Check:")
    print(f"   - User criteria count: {len(user_criteria_list)}")
    print(f"   - Feedback count: {len(feedback_list)}")
    
    if user_criteria_list:
        sample_criteria = user_criteria_list[0]
        print(f"   - Sample criteria attributes: {dir(sample_criteria)}")
        
    if feedback_list:
        sample_feedback = feedback_list[0]
        print(f"   - Sample feedback attributes: {dir(sample_feedback)}")
        print(f"   - Sample feedback: user_id={sample_feedback.user_id}, package_id={sample_feedback.package_id}, type={sample_feedback.feedback_type}")
    
    # 2. Cek unique package IDs dalam feedback
    all_package_ids = {fb.package_id for fb in feedback_list}
    liked_package_ids = {fb.package_id for fb in feedback_list if fb.feedback_type == 'like'}
    
    print(f"\n2. Package ID Analysis:")
    print(f"   - Total unique package IDs in feedback: {len(all_package_ids)}")
    print(f"   - Unique liked package IDs: {len(liked_package_ids)}")
    print(f"   - Sample package IDs: {list(all_package_ids)[:10]}")
    print(f"   - Sample liked package IDs: {list(liked_package_ids)[:10]}")
    
    # 3. Test sistem rekomendasi dengan sample criteria
    print(f"\n3. Recommendation System Test:")
    if user_criteria_list:
        sample_criteria = user_criteria_list[0]
        criteria_dict = {
            'kabupaten': sample_criteria.kabupaten.split(', ') if sample_criteria.kabupaten else [],
            'kategori_wisata': sample_criteria.kategori_wisata,
            'min_rating_tempat_wisata': sample_criteria.rating_tempat_wisata or 3.0,
            'min_rating_penginapan': sample_criteria.rating_penginapan or 3.0,
            'min_rating_rumah_makan': sample_criteria.rating_rumah_makan or 3.0,
            'min_harga_penginapan': 0,
            'max_harga_penginapan': sample_criteria.harga_penginapan or 1500000,
            'use_reviews': sample_criteria.metode_pencarian == 'Rating dan Ulasan',
            'num_recommendations': 10,
        }
        
        try:
            recommendations = get_recommendations_func(criteria_dict)
            print(f"   - Recommendations returned: {len(recommendations) if recommendations else 0}")
            
            if recommendations:
                rec_ids = [rec.get('recommendationId') for rec in recommendations]
                print(f"   - Sample recommendation IDs: {rec_ids[:5]}")
                print(f"   - Sample recommendation structure: {recommendations[0].keys() if recommendations else 'None'}")
                
                # Cek apakah ada overlap dengan liked items
                user_liked = {fb.package_id for fb in feedback_list if fb.user_id == sample_criteria.id_user and fb.feedback_type == 'like'}
                overlap = set(rec_ids) & user_liked
                print(f"   - User {sample_criteria.id_user} liked items: {list(user_liked)[:5]}")
                print(f"   - Overlap with recommendations: {list(overlap)}")
                
        except Exception as e:
            print(f"   - Error getting recommendations: {str(e)}")
    
    # 4. Rekomendasi perbaikan
    print(f"\n4. Recommendations for Fix:")
    print("   - Check if recommendation IDs match feedback package IDs format")
    print("   - Verify that get_recommendations_func returns correct data structure") 
    print("   - Ensure feedback and recommendation use same ID system")
    print("   - Consider if there's a data type mismatch (string vs int)")


# Fungsi tambahan untuk membandingkan ID formats
def compare_id_formats(recommendations, feedback_list):
    """
    Membandingkan format ID antara rekomendasi dan feedback
    """
    print("=== ID FORMAT COMPARISON ===")
    
    # Ambil sample IDs dari feedback
    feedback_ids = {fb.package_id for fb in feedback_list[:10]}
    feedback_id_types = {type(fb.package_id) for fb in feedback_list[:10]}
    
    print(f"Feedback ID samples: {list(feedback_ids)}")
    print(f"Feedback ID types: {feedback_id_types}")
    
    if recommendations:
        # Ambil sample IDs dari rekomendasi
        rec_ids = [rec.get('recommendationId') for rec in recommendations[:10]]
        rec_id_types = {type(rec_id) for rec_id in rec_ids if rec_id is not None}
        
        print(f"Recommendation ID samples: {rec_ids}")
        print(f"Recommendation ID types: {rec_id_types}")
        
        # Cek apakah ada perbedaan format
        if feedback_id_types != rec_id_types:
            print("WARNING: ID type mismatch detected!")
            print("This could be the cause of 0.0000 evaluation results")
    else:
        print("No recommendations to compare")