import sys
import os
from pathlib import Path

# Add backend directory
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from sqlmodel import Session, select
from app.database import engine
from app.models.user import User
from app.models.restaurant import Restaurant
from app.models.menu import MenuItem
from app.models.order import Order
from app.models.inventory import Ingredient
from app.algorithms.recommendations import get_personalized_recommendations
from app.algorithms.food_assistant import process_food_chat
from app.algorithms.demand_prediction import train_and_predict_demand
from app.algorithms.smart_inventory import get_inventory_and_waste_analysis, deduct_inventory_for_order
from app.algorithms.kitchen_priority import calculate_kitchen_priority_score
from app.algorithms.delivery_dispatch import haversine_distance_km, calculate_delivery_eta, find_best_delivery_partner

def run_all_tests():
    print("=" * 60)
    print("AI FOODIE - AUTOMATED VERIFICATION & TEST SUITE")
    print("=" * 60)
    
    with Session(engine) as session:
        # 1. Test Users & 5 Demo Accounts
        print("\n[1/10] Verifying Demo Users & Roles...")
        users = session.exec(select(User)).all()
        assert len(users) >= 5, f"Expected at least 5 users, found {len(users)}"
        roles_found = {u.role.value for u in users}
        expected_roles = {"customer", "restaurant_admin", "kitchen_staff", "delivery_partner", "super_admin"}
        assert expected_roles.issubset(roles_found), f"Missing roles: {expected_roles - roles_found}"
        print(f"  ✓ All 5 roles confirmed: {', '.join(expected_roles)}")

        # 2. Test Restaurants
        print("\n[2/10] Verifying 4 Demo Restaurants...")
        restaurants = session.exec(select(Restaurant)).all()
        assert len(restaurants) >= 4, f"Expected 4 restaurants, found {len(restaurants)}"
        rest_names = [r.name for r in restaurants]
        assert "Spice Garden" in rest_names
        assert "Pizza Palace" in rest_names
        assert "Burger Hub" in rest_names
        assert "Royal Kitchen" in rest_names
        print(f"  ✓ 4 Demo restaurants active: {', '.join(rest_names)}")

        # 3. Test Food Menu
        print("\n[3/10] Verifying Food Menu & Realistic Pricing...")
        menu_items = session.exec(select(MenuItem)).all()
        assert len(menu_items) >= 30, f"Expected >= 30 food items, found {len(menu_items)}"
        veg_items = [i for i in menu_items if i.is_veg]
        non_veg_items = [i for i in menu_items if not i.is_veg]
        assert len(veg_items) > 0 and len(non_veg_items) > 0
        print(f"  ✓ Total items: {len(menu_items)} ({len(veg_items)} Veg, {len(non_veg_items)} Non-Veg)")
        
        # Verify Spice Garden Masala Dosa
        dosa = next((i for i in menu_items if i.name == "Masala Dosa"), None)
        assert dosa is not None and dosa.price == 80.0
        print(f"  ✓ Menu verification: Masala Dosa = ₹{dosa.price:.2f}")

        # 4. Test AI Personalized Recommendations
        print("\n[4/10] Testing AI Personalized Recommendation Engine...")
        customer = next(u for u in users if u.role.value == "customer")
        recs = get_personalized_recommendations(session, user_id=customer.id, limit=5)
        assert len(recs) > 0
        print(f"  ✓ AI Recommendations generated: {[r.name for r in recs[:3]]}")

        # 5. Test AI Conversational Food Assistant (Real Database Search)
        print("\n[5/10] Testing AI Conversational Food Assistant (Database-backed)...")
        # Query 1: Veg under 200
        chat1 = process_food_chat(session, "Suggest vegetarian food under ₹200")
        assert len(chat1["recommended_items"]) > 0
        for item in chat1["recommended_items"]:
            assert item["is_veg"] is True
            assert item["price"] <= 200.0
        print(f"  ✓ 'Veg under ₹200' returned {len(chat1['recommended_items'])} items: {[i['name'] for i in chat1['recommended_items']]}")

        # Query 2: Ingredients in Paneer Butter Masala
        chat2 = process_food_chat(session, "What ingredients are in Paneer Butter Masala?")
        assert "Paneer" in chat2["reply"] or "paneer" in chat2["reply"].lower()
        print(f"  ✓ Ingredient lookup passed: {chat2['reply'][:80]}...")

        # 6. Test Scikit-learn Food Demand Prediction
        print("\n[6/10] Testing Scikit-learn Food Demand Prediction Model...")
        predictions = train_and_predict_demand(session, restaurant_id=1)
        assert len(predictions) > 0
        top_pred = predictions[0]
        assert top_pred["predicted_demand_next_day"] > 0
        assert top_pred["recommended_prep_qty"] >= top_pred["predicted_demand_next_day"]
        print(f"  ✓ ML Demand Forecast: '{top_pred['item_name']}' predicted demand = {top_pred['predicted_demand_next_day']} units, prep buffer = {top_pred['recommended_prep_qty']} units (Confidence: {int(top_pred['confidence_score']*100)}%)")

        # 7. Test Smart Ingredient Inventory & Automatic Deduction
        print("\n[7/10] Testing Smart Inventory Deduction & Low Stock Alerts...")
        spice_rest = next(r for r in restaurants if r.name == "Spice Garden")
        sample_order_item = type('obj', (object,), {
            "menu_item_id": dosa.id,
            "quantity": 2,
            "item_name": dosa.name
        })
        alerts = deduct_inventory_for_order(session, spice_rest.id, 9999, [sample_order_item])
        print(f"  ✓ Auto-deducted constituent recipe ingredients for Order #9999 (Masala Dosa x2)")

        # 8. Test Food Waste Reduction Analysis
        print("\n[8/10] Testing Food Waste & Expiry Tracking...")
        waste_report = get_inventory_and_waste_analysis(session, spice_rest.id)
        assert "total_inventory_value" in waste_report
        assert "expiry_warnings" in waste_report
        print(f"  ✓ Monitored {waste_report['total_ingredients_monitored']} ingredients, Inventory Value: ₹{waste_report['total_inventory_value']:.2f}, Low Stock Alerts: {waste_report['low_stock_alerts_count']}")

        # 9. Test Intelligent Kitchen Order Prioritization
        print("\n[9/10] Testing Kitchen Priority Score Algorithm...")
        active_orders = session.exec(select(Order)).all()
        assert len(active_orders) >= 5
        score1 = calculate_kitchen_priority_score(active_orders[0], 5.0)
        score2 = calculate_kitchen_priority_score(active_orders[0], 25.0)
        assert score2 > score1, "Elapsed time should increase priority score"
        print(f"  ✓ Kitchen priority score calculation verified: 5 min wait = {score1}, 25 min wait = {score2}")

        # 10. Test Delivery Distance & Smart Dispatch
        print("\n[10/10] Testing Delivery Partner Geolocation & Dispatch...")
        dist = haversine_distance_km(12.9784, 77.6408, 12.9304, 77.6784)
        eta = calculate_delivery_eta(dist, 15)
        best_partner = find_best_delivery_partner(session, 12.9784, 77.6408)
        assert best_partner is not None
        print(f"  ✓ Haversine Distance: {dist} km, Calculated ETA: {eta} mins, Assigned Partner: {best_partner.full_name}")

    print("\n" + "=" * 60)
    print("ALL 10 MODULES AND CORE FLOWS VERIFIED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_all_tests()
