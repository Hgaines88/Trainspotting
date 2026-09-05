PRAGMA foreign_keys = ON;

INSERT INTO designers (
    id,
    full_name,
    nationality,
    birth_year,
    website,
    biography
)
VALUES
    (
        1,
        'Sarah Burton',
        'British',
        NULL,
        NULL,
        'Fashion designer whose career includes work for Alexander McQueen and Givenchy.'
    ),
    (
        2,
        'Shayne Oliver',
        'American',
        NULL,
        NULL,
        'Fashion designer associated with multiple labels and creative projects.'
    ),
    (
        3,
        'Grace Wales Bonner',
        'British-Jamaican',
        NULL,
        'https://walesbonner.com',
        'Founder of Wales Bonner, a label exploring European heritage and Afro-Atlantic cultural traditions.'
    ),
    (
        4,
        'Lee Alexander McQueen',
        'British',
        NULL,
        'https://www.alexandermcqueen.com',
        'Founder of the McQueen house, known for innovative tailoring and theatrical presentations.'
    ),
    (
        5,
        'Jonathan Anderson',
        'Northern Irish',
        NULL,
        'https://jwanderson.com',
        'Founder of JW Anderson whose career includes creative leadership at Loewe and Dior.'
    ),
    (
        6,
        'Demna',
        'Georgian',
        NULL,
        NULL,
        'Designer and co-founder of Vetements whose career includes creative leadership at Balenciaga and Gucci.'
    ),
    (
        7,
        'Virgil Abloh',
        'American',
        NULL,
        NULL,
        'Designer and founder of Off-White whose career includes creative leadership at Louis Vuitton.'
    ),
    (
        8,
        'Junya Watanabe',
        'Japanese',
        1961,
        NULL,
        'Designer who began his career at Comme des Garçons and launched his namesake line within the house.'
    ),
    (
        9,
        'Miuccia Prada',
        'Italian',
        NULL,
        NULL,
        'Designer and creative director of Prada and Miu Miu.'
    ),
    (
        10,
        'Rei Kawakubo',
        'Japanese',
        NULL,
        NULL,
        'Designer and founder of Comme des Garçons.'
    ),
    (
        11,
        'Telfar Clemens',
        'Liberian-American',
        1985,
        'https://telfar.net',
        'Founder of Telfar, a New York label known for accessible, unisex fashion and its community-focused approach.'
    ),
    (
        12,
        'Rick Owens',
        'American',
        1962,
        'https://www.rickowens.eu',
        'California-born designer who founded his independent namesake label in 1994 and later established it in Paris.'
    );


INSERT INTO collections (
    id,
    designer_id,
    label,
    name,
    season,
    release_year,
    status,
    piece_count,
    description
)
VALUES (
            1,
            1,
            'Givenchy',
            NULL,
            'Fall/Winter',
            2025,
            'released',
            52,
            'The collection focused on cut, proportion, and tailoring.'
        ),
        (
            2,
            1,
            'Alexander McQueen',
            NULL,
            'Spring/Summer',
            2024,
            'archived',
            NULL,
            'Sarah Burton''s final collection as creative director of Alexander McQueen.'
        ),
        (
            3,
            2,
            'Hood By Air',
            'Pilgrimage',
            'Fall/Winter',
            2016,
            'archived',
            NULL,
            'A collection exploring transience, migration, and the body as cargo.'
        ),
        (
            4,
            3,
            'Wales Bonner',
            NULL,
            'Spring/Summer',
            2024,
            'released',
            34,
            'The Spring/Summer 2024 menswear collection was titled Marathon.'
        ),
        (
            5,
            4,
            'Alexander McQueen',
            'No. 13',
            'Spring/Summer',
            1999,
            'archived',
            NULL,
            'A landmark Lee Alexander McQueen collection known for its theatrical runway presentation.'
        ),
        (
            6,
            5,
            'JW Anderson',
            NULL,
            'Spring/Summer',
            2024,
            'released',
            NULL,
            'The collection reworked familiar wardrobe pieces with exaggerated proportions and unexpected materials.'
        ),
        (
            7,
            2,
            'Hood By Air',
            'Wench',
            'Spring/Summer',
            2017,
            'archived',
            NULL,
            'A Hood By Air collection developed with Wench, Shayne Oliver and Arca''s musical project.'
        ),
        (
            8,
            2,
            'Helmut Lang',
            'Seen by Shayne Oliver',
            'Spring/Summer',
            2018,
            'archived',
            NULL,
            'Created during Shayne Oliver''s residency at Helmut Lang.'
        ),
        (
            9,
            2,
            'Diesel',
            'Red Tag Project',
            'Fall/Winter',
            2018,
            'archived',
            NULL,
            'A denim-focused capsule created for the Diesel Red Tag Project.'
        ),
    (
        10,
        6,
        'Balenciaga',
        NULL,
        'Spring/Summer',
        2023,
        'archived',
        NULL,
        'A Demna collection presented on a mud-covered runway in Paris.'
    ),
    (
        11,
        7,
        'Louis Vuitton',
        NULL,
        'Spring/Summer',
        2019,
        'archived',
        NULL,
        'Virgil Abloh''s debut menswear collection for Louis Vuitton.'
    ),
    (
        12,
        8,
        'Junya Watanabe MAN',
        NULL,
        'Spring/Summer',
        2025,
        'archived',
        NULL,
        'A menswear collection combining formalwear with a punk sensibility.'
    ),
    (
        13,
        9,
        'Prada',
        NULL,
        'Spring/Summer',
        2012,
        'archived',
        NULL,
        'A Miuccia Prada collection drawing on 1950s automobile imagery.'
    ),
    (
        14,
        10,
        'Comme des Garçons',
        'Body Meets Dress, Dress Meets Body',
        'Spring/Summer',
        1997,
        'archived',
        NULL,
        'Rei Kawakubo challenged conventional silhouettes using asymmetrical padded forms.'
    ),
    (
        15,
        2,
        'Anonymous Club',
        NULL,
        'Resort',
        2024,
        'archived',
        NULL,
        'The second Anonymous Club installment presented wardrobe staples through Shayne Oliver''s design language.'
    ),
    (
        16,
        11,
        'Telfar',
        NULL,
        'Spring/Summer',
        2020,
        'archived',
        NULL,
        'A Paris presentation pairing the collection with the collaborative film The World Isn''t Everything.'
    ),
    (
        17,
        12,
        'Rick Owens',
        'Vicious',
        'Spring/Summer',
        2014,
        'archived',
        40,
        'A presentation performed by four step teams that challenged conventional runway casting and beauty standards.'
    );

INSERT INTO collection_credits (
    collection_id, designer_id, credit_role, credit_order
)
SELECT collections.id, collections.designer_id, 'lead', 1
FROM collections
WHERE NOT EXISTS (
    SELECT 1
    FROM collection_credits
    WHERE collection_credits.collection_id = collections.id
);
