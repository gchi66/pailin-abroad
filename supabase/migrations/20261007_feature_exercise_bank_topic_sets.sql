-- Keep the curated Exercise Bank landing-page selection in source control.
update public.exercise_bank_topics
set is_featured = true
where is_active = true
  and source_key in (
    'dfa51eed728f67bc8ef263498db208e3', -- Pailin is hungry
    '1533b5801b499f3dd999c4742bf0c4c0', -- We went to France
    'ac842205e274e551436e725c1bf7a2d3', -- I have a dog
    '7df7e03d16173a7c82e7378dd87d88e9', -- There’s a gas station
    '299fc623a7a241504605597b924a506b', -- They’re bored
    '1eb7b657bd420d5584e22a9fa996ba44', -- He’s older than you
    '0135dbcd38285ec37a904cf3ce5acc29', -- Let’s talk to them
    'c9d2cce018fabc5e4ba4c0bb3c56ca9a'  -- I live on the 4th floor
  );
