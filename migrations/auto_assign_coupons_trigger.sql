-- Automate Coupon Assignment on User Creation
-- This ensures that every new user immediately gets a random set of coupons assigned.

-- 1. Create the function to assign random coupons
CREATE OR REPLACE FUNCTION public.assign_registration_coupons(new_user_id UUID)
RETURNS VOID AS $$
BEGIN
    -- Assign 2 random frontstore coupons
    INSERT INTO public.user_coupons (user_id, coupon_id, eligible_until)
    SELECT 
        new_user_id, 
        id, 
        NOW() + INTERVAL '14 days'
    FROM public.coupons
    WHERE type = 'frontstore' 
      AND expiration_date > NOW()
    ORDER BY RANDOM()
    LIMIT 2
    ON CONFLICT (user_id, coupon_id) DO NOTHING;

    -- Assign 30 random category/brand coupons
    INSERT INTO public.user_coupons (user_id, coupon_id, eligible_until)
    SELECT 
        new_user_id, 
        id, 
        NOW() + INTERVAL '14 days'
    FROM public.coupons
    WHERE type IN ('category', 'brand') 
      AND expiration_date > NOW()
    ORDER BY RANDOM()
    LIMIT 30
    ON CONFLICT (user_id, coupon_id) DO NOTHING;
END;
$$ LANGUAGE plpgsql;

-- 2. Create the trigger function
CREATE OR REPLACE FUNCTION public.trigger_assign_coupons_on_insert()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM public.assign_registration_coupons(NEW.id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. Create the trigger on public.users
DROP TRIGGER IF EXISTS on_user_created_assign_coupons ON public.users;

CREATE TRIGGER on_user_created_assign_coupons
    AFTER INSERT ON public.users
    FOR EACH ROW
    EXECUTE FUNCTION public.trigger_assign_coupons_on_insert();

-- 4. Optional Backfill: Assign coupons to any existing users who have 0 coupons
-- This is safe to run as the function has ON CONFLICT DO NOTHING
DO $$
DECLARE
    user_rec RECORD;
BEGIN
    FOR user_rec IN 
        SELECT u.id 
        FROM public.users u 
        LEFT JOIN public.user_coupons uc ON u.id = uc.user_id 
        GROUP BY u.id 
        HAVING COUNT(uc.id) = 0
    LOOP
        PERFORM public.assign_registration_coupons(user_rec.id);
    END LOOP;
END $$;

