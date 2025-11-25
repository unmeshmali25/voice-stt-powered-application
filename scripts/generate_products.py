import csv
import random

# Product catalog organized by category with realistic CVS products
catalog = {
    "Health": [
        ("Advil Liqui-Gels 200mg", "Fast-acting pain reliever and fever reducer. Ibuprofen liquid-filled capsules for headaches, muscle aches, and minor arthritis pain. 80 softgels.", 14.99, "Advil"),
        ("Aleve Naproxen Sodium Tablets", "All day strong pain relief. 12-hour pain relief for minor aches and pains. 220mg, 100 caplets.", 13.49, "Aleve"),
        ("Bayer Aspirin Low Dose 81mg", "Safety coated aspirin for heart health and pain relief. Doctor recommended for cardiovascular support. 120 tablets.", 8.99, "Bayer"),
        ("Motrin IB Tablets", "Ibuprofen pain reliever and fever reducer for body aches and headaches. 200mg, 50 tablets.", 9.99, "Motrin"),
        ("Excedrin Extra Strength", "Triple action formula for headache relief. Contains acetaminophen, aspirin, and caffeine. 100 caplets.", 11.99, "Excedrin"),
        ("Tylenol PM Extra Strength", "Nighttime pain reliever and sleep aid. Acetaminophen 500mg with diphenhydramine. 100 caplets.", 12.99, "Tylenol"),
        ("Sudafed PE Sinus Pressure + Pain", "Non-drowsy decongestant for sinus pressure and congestion relief. Phenylephrine HCl. 24 tablets.", 10.49, "Sudafed"),
        ("Robitussin Maximum Strength Cough", "Cough suppressant and expectorant. Relieves chest congestion and controls cough. 8 fl oz.", 12.99, "Robitussin"),
        ("Halls Cough Drops Honey Lemon", "Soothing throat drops with menthol and natural honey lemon flavor. 30 drops per bag.", 3.49, "Halls"),
        ("NyQuil Cold & Flu Nighttime Relief", "Multi-symptom cold and flu relief. Reduces fever, relieves aches, and helps you rest. 12 fl oz.", 13.99, "Vicks"),
    ],
    "Beauty": [
        ("Maybelline Fit Me Matte + Poreless Foundation", "Lightweight liquid foundation for normal to oily skin. Refines pores and controls shine. SPF 18. 1 fl oz.", 8.99, "Maybelline"),
        ("Revlon Super Lustrous Lipstick", "High-impact color with a creamy, moisturizing formula. Vitamin E and avocado oil. 0.15 oz.", 9.99, "Revlon"),
        ("L'Oreal Paris Infallible Pro-Matte Liquid Lipstick", "16-hour wear liquid lipstick with intense matte finish. Transfer-resistant formula. 0.21 fl oz.", 11.99, "L'Oreal Paris"),
        ("NYX Professional Makeup Epic Ink Liner", "Waterproof liquid eyeliner with precision brush tip. Intense black pigment. 0.03 fl oz.", 9.49, "NYX Professional"),
        ("e.l.f. Poreless Putty Primer", "Velvety makeup primer that grips makeup for all-day wear. Minimizes pores and fine lines. 0.74 oz.", 10.00, "e.l.f."),
        ("Physician's Formula Butter Bronzer", "Murumuru butter-infused bronzer for a natural sun-kissed glow. Hypoallergenic. 0.38 oz.", 14.95, "Physician's Formula"),
        ("Wet n Wild MegaGlo Highlighting Powder", "Radiant highlighting powder with light-reflecting pearls. Buildable shimmer. 0.19 oz.", 5.99, "Wet n Wild"),
        ("Essence Lash Princess False Lash Mascara", "Volumizing and defining mascara with conic fiber brush. Dramatic lash effect. 0.42 fl oz.", 4.99, "Essence"),
        ("CoverGirl Clean Fresh Skin Milk Foundation", "Lightweight hydrating foundation with 2% hyaluronic acid. Medium coverage. 1 fl oz.", 11.99, "CoverGirl"),
        ("Rimmel London Stay Matte Powder", "Long-lasting pressed powder controls shine for up to 5 hours. Natural matte finish. 0.49 oz.", 6.99, "Rimmel London"),
    ],
    "Vitamins": [
        ("Nature Made Vitamin C 500mg", "Immune support supplement with powerful antioxidant. USP verified. 100 tablets.", 11.99, "Nature Made"),
        ("One A Day Men's Multivitamin", "Complete multivitamin for men's health support. Vitamins A, C, D, E, B vitamins. 200 tablets.", 16.99, "One A Day"),
        ("Vitafusion Vitamin D3 Gummies", "Delicious peach, blackberry & strawberry flavored vitamin D gummies. 2000 IU. 75 gummies.", 10.99, "Vitafusion"),
        ("Centrum Adults Multivitamin/Multimineral Supplement", "Complete daily multivitamin with 23 essential nutrients. Supports immune health. 100 tablets.", 14.49, "Centrum"),
        ("Nature's Bounty Hair Skin and Nails Gummies", "Beauty supplement with biotin, vitamins C & E. Supports healthy hair, radiant skin. 80 gummies.", 12.99, "Nature's Bounty"),
        ("Calcium 600mg + D3", "Bone health supplement. Calcium carbonate with vitamin D3 for enhanced absorption. 200 softgels.", 13.99, "Nature Made"),
        ("Omega-3 Fish Oil 1200mg", "Heart health support with EPA and DHA omega-3 fatty acids. Purified for purity. 100 softgels.", 18.99, "Nature Made"),
        ("Nature's Bounty B-12 Sublingual", "Energy support vitamin B12. Fast dissolving cherry flavored tablets. 2500 mcg, 75 tablets.", 14.99, "Nature's Bounty"),
        ("Airborne Elderberry + Zinc Gummies", "Immune support with vitamin C, zinc, and elderberry extract. Mixed berry flavor. 63 gummies.", 17.99, "Airborne"),
        ("Nature's Truth Turmeric Curcumin", "Anti-inflammatory supplement with black pepper extract for absorption. 500mg, 60 capsules.", 15.99, "Nature's Truth"),
    ],
    "Personal Care": [
        ("Dove Men+Care Body Wash", "Hydrating body and face wash with MICROMOISTURE technology. Clean comfort scent. 18 fl oz.", 7.99, "Dove"),
        ("Degree Men MotionSense Antiperspirant", "72-hour sweat and odor protection. Motion-activated fresh scent. 2.7 oz stick.", 5.99, "Degree"),
        ("Suave Professionals Shampoo Coconut Oil Infusion", "Moisturizing shampoo for dry, damaged hair. Infused with pure coconut oil. 28 fl oz.", 4.99, "Suave"),
        ("TRESemmé Keratin Smooth Conditioner", "Professional quality conditioner for smooth, shiny hair. Controls frizz for 72 hours. 28 fl oz.", 5.99, "TRESemmé"),
        ("Garnier Fructis Sleek & Shine Anti-Frizz Serum", "Argan oil hair serum for frizz control and shine. Heat protectant. 5.1 fl oz.", 6.99, "Garnier"),
        ("Axe Body Spray Phoenix", "Crushed mint and rosemary body spray for men. Long-lasting fragrance. 4 oz.", 6.49, "Axe"),
        ("Secret Clinical Strength Antiperspirant", "Prescription-strength wetness protection. Stress-tested formula. 1.6 oz stick.", 11.99, "Secret"),
        ("Gillette Fusion5 ProGlide Razor Blades", "Men's razor blade refills with 5 anti-friction blades. Precision trimmer. 8 cartridges.", 32.99, "Gillette"),
        ("Schick Intuition Sensitive Care Razor", "Women's razor with built-in shave gel. Hypoallergenic moisturizers. 1 handle + 2 cartridges.", 11.99, "Schick"),
        ("Colgate Optic White Whitening Toothpaste", "Teeth whitening toothpaste removes 10 years of stains. Enamel-safe formula. 4.2 oz.", 6.49, "Colgate"),
    ],
    "Sunscreen": [
        ("Neutrogena Ultra Sheer Dry-Touch Sunscreen SPF 55", "Lightweight, non-greasy sunscreen with Helioplex technology. Water-resistant 80 minutes. 3 fl oz.", 11.99, "Neutrogena"),
        ("Coppertone Sport Sunscreen SPF 50", "Water-resistant sport sunscreen stays on strong when you sweat. Broad spectrum UVA/UVB. 7 fl oz.", 10.99, "Coppertone"),
        ("Hawaiian Tropic Sheer Touch Sunscreen SPF 30", "Ultra-light, breathable sunscreen with island botanicals. Oil-free formula. 8 fl oz.", 9.99, "Hawaiian Tropic"),
        ("Banana Boat Kids Sunscreen Spray SPF 50", "Tear-free, sting-free sunscreen for kids. Water-resistant 80 minutes. 6 oz continuous spray.", 10.49, "Banana Boat"),
        ("Sun Bum Original Sunscreen Lotion SPF 50", "Hypoallergenic broad spectrum protection. Vegan, reef-friendly formula. 3 fl oz.", 14.99, "Sun Bum"),
    ],
    "Lip Balm": [
        ("ChapStick Classic Cherry", "Moisturizes and protects lips from dryness. SPF 15 sun protection. 0.15 oz stick.", 2.99, "ChapStick"),
        ("EOS Organic Lip Balm Sweet Mint", "USDA organic shea butter lip balm. Long-lasting moisture. 0.25 oz sphere.", 3.99, "EOS"),
        ("Blistex Medicated Lip Balm", "Medicated relief for dry, chapped lips. Soothes and protects. 0.15 oz.", 2.49, "Blistex"),
        ("Carmex Classic Lip Balm", "Moisturizing lip balm with camphor and menthol. Soothes cold sores. 0.25 oz jar.", 2.99, "Carmex"),
        ("Vaseline Lip Therapy Original", "Pure petroleum jelly lip balm for soft, healthy lips. Clinically proven. 0.25 oz tin.", 3.49, "Vaseline"),
    ],
    "Facewash": [
        ("La Roche-Posay Toleriane Hydrating Gentle Cleanser", "Creamy face wash for normal to dry sensitive skin. Prebiotic thermal water. 13.52 fl oz.", 15.99, "La Roche-Posay"),
        ("Cetaphil Daily Facial Cleanser", "Gentle foaming cleanser for all skin types. Removes dirt, oil, and makeup. 16 fl oz.", 10.99, "Cetaphil"),
        ("Clean & Clear Morning Burst Facial Cleanser", "Energizing citrus scent face wash with bursting beads. Oil-free formula. 8 fl oz.", 6.99, "Clean & Clear"),
        ("Aveeno Clear Complexion Foaming Cleanser", "Salicylic acid acne treatment cleanser with soy extract. Oil-free. 6 fl oz.", 8.99, "Aveeno"),
    ],
    "Serum": [
        ("The Ordinary Niacinamide 10% + Zinc 1%", "High-strength vitamin and mineral blemish formula. Reduces appearance of pores. 1 fl oz.", 6.99, "The Ordinary"),
        ("Neutrogena Rapid Wrinkle Repair Serum", "Anti-aging serum with accelerated retinol SA. Visibly reduces wrinkles. 1 fl oz.", 26.99, "Neutrogena"),
        ("L'Oreal Paris Revitalift Derm Intensives Vitamin C Serum", "Brightening face serum with 10% pure vitamin C. Reduces dark spots. 1 fl oz.", 24.99, "L'Oreal Paris"),
        ("CeraVe Skin Renewing Vitamin C Serum", "Antioxidant serum with hyaluronic acid and ceramides. Brightens skin tone. 1 fl oz.", 19.99, "CeraVe"),
    ],
    "Cleaning Products": [
        ("Lysol Disinfectant Spray Crisp Linen", "Kills 99.9% of viruses and bacteria. Eliminates odors on soft surfaces. 19 oz spray.", 7.99, "Lysol"),
        ("Clorox Disinfecting Wipes Bleach Free", "Multi-surface cleaning wipes kill 99.9% of germs. Fresh scent. 75 count canister.", 5.49, "Clorox"),
        ("Method All-Purpose Cleaner French Lavender", "Plant-based formula for streak-free cleaning. Biodegradable, non-toxic. 28 fl oz spray.", 4.99, "Method"),
        ("Mr. Clean Magic Eraser Extra Durable", "Water-activated micro-scrubbers remove tough dirt. Chemical-free cleaning. 2 pads.", 4.49, "Mr. Clean"),
        ("Pledge Furniture Spray Lemon", "Wood polish cleans and protects furniture. Improves wood's natural beauty. 9.7 oz aerosol.", 5.99, "Pledge"),
        ("Windex Original Glass Cleaner", "Streak-free shine on glass, windows, and mirrors. Ammonia-D formula. 23 fl oz spray.", 4.49, "Windex"),
        ("Scrubbing Bubbles Bathroom Cleaner", "Foaming bathroom cleaner removes soap scum and grime. Penetrating foam. 25 oz aerosol.", 4.99, "Scrubbing Bubbles"),
    ],
    "Laundry": [
        ("Tide Liquid Laundry Detergent Original Scent", "America's #1 detergent for deep cleaning. HE compatible. 64 loads, 92 fl oz.", 18.99, "Tide"),
        ("Gain Flings Laundry Detergent Pacs", "3-in-1 detergent, Oxi boost, and Febreze freshness. Original scent. 42 count.", 16.99, "Gain"),
        ("Arm & Hammer Clean Burst Liquid Laundry Detergent", "Odor blasters with baking soda. Fresh clean scent. HE compatible. 75 fl oz, 50 loads.", 9.99, "Arm & Hammer"),
        ("Downy Infusions Fabric Softener Calm", "Liquid fabric conditioner with lavender and vanilla bean. 83 fl oz, 89 loads.", 10.99, "Downy"),
        ("OxiClean Versatile Stain Remover Powder", "Oxygen-powered stain fighter for laundry and household. Chlorine-free. 3 lbs.", 12.99, "OxiClean"),
        ("Shout Advanced Stain Remover Gel", "Triple-acting stain remover for tough stains. Works on set-in stains. 22 fl oz.", 5.99, "Shout"),
        ("Woolite Delicates Laundry Detergent", "Gentle formula for hand wash and delicate fabrics. Maintains shape. 50 fl oz, 25 loads.", 8.99, "Woolite"),
    ],
    "Paper Products": [
        ("Scott 1000 Toilet Paper", "Long-lasting bath tissue, 1000 sheets per roll. Septic-safe, clog-free. 12 rolls.", 15.99, "Scott"),
        ("Kleenex Ultra Soft Facial Tissues", "3-ply soft facial tissues. Absorbent and gentle. 120 tissues per box, 4 boxes.", 7.99, "Kleenex"),
        ("Viva Signature Cloth Paper Towels", "Stretchy, cloth-like paper towels. Strong when wet. Choose-a-size. 6 rolls.", 13.99, "Viva"),
        ("Quilted Northern Ultra Plush Toilet Paper", "3-ply premium bath tissue. Soft and strong. 12 mega rolls = 48 regular rolls.", 19.99, "Quilted Northern"),
        ("Puffs Plus Lotion Facial Tissues", "Soft tissues with lotion for soothing relief. Dermatologist tested. 124 tissues, 3 boxes.", 6.99, "Puffs"),
    ],
    "First Aid": [
        ("Band-Aid Brand Flexible Fabric Adhesive Bandages", "Quilt-Aid comfort pad cushions painful wounds. Stays on for up to 24 hours. 100 count.", 7.99, "Band-Aid"),
        ("Neosporin Original Antibiotic Ointment", "Triple antibiotic ointment prevents infection in minor cuts and burns. 1 oz tube.", 8.99, "Neosporin"),
        ("Curad Assorted Bandages", "Variety pack of bandages for different wound sizes. Non-stick pad. 300 count.", 9.99, "Curad"),
        ("Polysporin First Aid Antibiotic Ointment", "Dual antibiotic ointment for infection prevention. Bacitracin & polymyxin B. 1 oz.", 7.49, "Polysporin"),
        ("3M Nexcare Waterproof Bandages", "Clear, waterproof protection for minor wounds. Stays on in water. 50 count.", 6.99, "Nexcare"),
    ],
    "Baby Care": [
        ("Pampers Swaddlers Disposable Diapers Size 1", "Softest diaper with blanket-like softness. Absorbs wetness and runny mess. 84 count.", 29.99, "Pampers"),
        ("Huggies Natural Care Sensitive Baby Wipes", "Hypoallergenic wipes with aloe and vitamin E. Fragrance-free. 168 wipes, 3 packs.", 11.99, "Huggies"),
        ("Desitin Maximum Strength Diaper Rash Paste", "40% zinc oxide for severe diaper rash relief. Pediatrician recommended. 4 oz.", 9.99, "Desitin"),
        ("Johnson's Baby Shampoo", "Gentle, tear-free formula for baby's delicate hair and scalp. Hypoallergenic. 13.6 fl oz.", 5.99, "Johnson's Baby"),
        ("Boudreaux's Butt Paste Diaper Rash Ointment", "Pediatrician-developed formula with 16% zinc oxide. Paraben-free. 4 oz.", 8.99, "Boudreaux's"),
    ],
    "Snacks": [
        ("KIND Bars Dark Chocolate Nuts & Sea Salt", "Gluten-free snack bars with whole nuts and dark chocolate. 5g protein. 12 bars.", 14.99, "KIND"),
        ("Nature Valley Crunchy Granola Bars Oats 'n Honey", "Wholesome granola bars with whole grain oats. 100% natural. 12 bars, 6 pouches.", 5.99, "Nature Valley"),
        ("Planters Dry Roasted Peanuts", "Classic roasted peanuts with sea salt. Good source of protein. 16 oz jar.", 7.99, "Planters"),
        ("Goldfish Cheddar Crackers", "Baked snack crackers with real cheese. No artificial flavors. 30 oz carton.", 9.99, "Goldfish"),
    ],
    "Beverages": [
        ("Gatorade Thirst Quencher Variety Pack", "Replenishes electrolytes lost in sweat. 4 flavors. 12 fl oz bottles, 12 pack.", 11.99, "Gatorade"),
        ("Fiji Natural Artesian Water", "Natural artesian water from Fiji. Soft, smooth taste. 16.9 fl oz bottles, 6 pack.", 7.99, "Fiji"),
        ("Red Bull Energy Drink", "Energy drink with caffeine, taurine, and B vitamins. Original formula. 8.4 fl oz, 4 pack.", 7.99, "Red Bull"),
    ],
    "Batteries": [
        ("Energizer MAX Alkaline AA Batteries", "Long-lasting power for everyday devices. Leak-proof design. 24 pack.", 16.99, "Energizer"),
        ("Duracell Coppertop AAA Batteries", "Reliable power for household electronics. 10-year guarantee. 16 pack.", 14.99, "Duracell"),
        ("Energizer Ultimate Lithium AA Batteries", "World's longest lasting AA battery. Performs in extreme temperatures. 8 pack.", 13.99, "Energizer"),
    ],
}

# Promotional text options
promos = [
    "Buy 1, Get 1 50% Off",
    "Buy 2, Get 1 Free",
    "$2 off",
    "$5 off $20",
    "Save $3",
    "Spend $15, Get $5 ExtraBucks",
    "",
    "",
    "",
    ""
]

def generate_slug(name):
    """Convert product name to kebab-case filename"""
    slug = name.lower()
    slug = slug.replace("'", "").replace("+", "plus").replace("&", "and")
    slug = slug.replace("%", "pct").replace("/", "-")
    # Remove special characters
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789- "
    slug = "".join(c if c in allowed else "" for c in slug)
    slug = "-".join(slug.split())
    return f"{slug}.jpg"

def generate_products():
    """Generate diverse product list with variations"""
    products = []

    for category, items in catalog.items():
        for base_name, base_desc, base_price, brand in items:
            # Add base product
            products.append({
                "name": base_name,
                "description": base_desc,
                "price": base_price,
                "brand": brand,
                "category": category,
            })

            # Add some variations (about 30% get variations)
            if random.random() < 0.3:
                variation_type = random.choice(["Twin Pack", "Value Pack", "Travel Size"])

                if variation_type == "Twin Pack":
                    var_name = f"{base_name} (Twin Pack)"
                    var_desc = f"Convenient twin pack. {base_desc}"
                    var_price = round(base_price * 1.85, 2)
                elif variation_type == "Value Pack":
                    var_name = f"{base_name} (Value Pack)"
                    var_desc = f"Extra value size. {base_desc}"
                    var_price = round(base_price * 2.2, 2)
                else:  # Travel Size
                    var_name = f"{base_name} (Travel Size)"
                    var_desc = f"TSA-approved travel size. {base_desc[:100]}..."
                    var_price = round(base_price * 0.45, 2)

                products.append({
                    "name": var_name,
                    "description": var_desc,
                    "price": var_price,
                    "brand": brand,
                    "category": category,
                })

    # Generate final CSV rows with randomized attributes
    rows = []
    for product in products:
        rating = round(random.uniform(3.8, 5.0), 1)
        reviews = random.randint(50, 20000)
        promo = random.choice(promos)
        image_filename = generate_slug(product["name"])

        row = [
            product["name"],
            product["description"],
            image_filename,
            f"{product['price']:.2f}",
            f"{rating:.1f}",
            str(reviews),
            product["category"],
            product["brand"],
            promo,
            "TRUE"
        ]
        rows.append(row)

    return rows

if __name__ == "__main__":
    print("Generating CVS products...")

    products = generate_products()

    print(f"Generated {len(products)} products")
    print("\nSample products:")
    for i, product in enumerate(products[:5], 1):
        print(f"{i}. {product[0]} - ${product[3]} ({product[6]})")

    # Write to a temporary CSV file
    headers = ["name", "description", "image_filename", "price", "rating", "review_count", "category", "brand", "promo_text", "in_stock"]
    output_file = "/Users/unmeshmali/Downloads/Unmesh/VoiceOffers/data/new_products_generated.csv"

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(headers)
        writer.writerows(products)

    print(f"\n✓ Products written to: {output_file}")
    print(f"Total products: {len(products)}")
    print("\nTo append to products.csv, this script will be used in the next step.")
