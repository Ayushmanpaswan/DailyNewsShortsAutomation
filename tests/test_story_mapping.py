import unittest

from licensed_images import _relevance, search_queries, story_mapping


class StoryMappingTests(unittest.TestCase):
    def test_hindi_person_and_event_make_focused_query(self):
        item = {"headline": "प्रधानमंत्री नरेंद्र मोदी की जापान यात्रा", "detail": "भारत के प्रधानमंत्री नरेंद्र मोदी आधिकारिक दौरे पर गए।"}
        mapping = story_mapping(item)
        self.assertEqual(mapping["status"], "ready")
        self.assertIn("Narendra Modi official visit", search_queries(item))
        self.assertNotIn("India news", search_queries(item))

    def test_indian_institutions_places_and_medical_topics_are_explicit(self):
        item = {"headline": "एम्स दिल्ली में टीबी जांच अभियान", "detail": "अस्पताल में मरीजों की जांच और टीकाकरण हुआ।"}
        mapping = story_mapping(item)
        self.assertCountEqual(mapping["entity_terms"], ["AIIMS", "Delhi"])
        self.assertIn("AIIMS tuberculosis", mapping["queries"])
        self.assertIn("AIIMS hospital", mapping["queries"])
        self.assertIn("AIIMS vaccination", mapping["queries"])

    def test_missing_sides_are_auditable(self):
        entity_only = story_mapping({"headline": "राहुल गांधी ने बयान दिया", "detail": "नई दिल्ली में पत्रकारों से बात की।"})
        self.assertEqual(entity_only["status"], "rejected")
        self.assertIn("event/context", entity_only["rejection_reason"])
        context_only = story_mapping({"headline": "भारी बारिश से बाढ़", "detail": "कई इलाकों में पानी भर गया।"})
        self.assertEqual(context_only["status"], "rejected")
        self.assertIn("entity", context_only["rejection_reason"])

    def test_relevance_requires_both_independent_metadata_matches(self):
        item = {"headline": "इसरो का प्रक्षेपण", "detail": "इसरो ने प्रक्षेपण की तैयारी की।"}
        metadata = {"ObjectName": {"value": "Indian Space Research Organisation"}, "ImageDescription": {"value": "rocket"}}
        page = {"title": "File:ISRO rocket.jpg", "categories": []}
        self.assertIsNone(_relevance(item, page, metadata))
        metadata["ImageDescription"] = {"value": "Indian Space Research Organisation launch"}
        self.assertIsNotNone(_relevance(item, page, metadata))

    def test_recent_rss_variants_have_explicit_focused_pairs(self):
        stories = [
            {"headline": "शाहरुख-काजोल के गाने पर झूमी जॉर्जिया की लड़की", "detail": "शाहरुख-काजोल के गाने पर डांस वाले वीडियो पर व्यूज आए।"},
            {"headline": "बहरीन में अमेरिकी रडार पर हमला; ईरान का दावा", "detail": "ईरान की IRGC ने हमले का दावा किया।"},
            {"headline": "दिल्ली से पटना इलेक्ट्रिक कार लॉन्च", "detail": "BYD के सब-ब्रांड डेंजा ने नई इलेक्ट्रिक SUV लॉन्च की।"},
            {"headline": "ओला पर एक्शन, CCPA ने ठोका जुर्माना", "detail": "केंद्रीय उपभोक्ता संरक्षण प्राधिकरण ने ANI Technologies पर जुर्माना लगाया।"},
        ]
        for item in stories:
            mapping = story_mapping(item)
            self.assertEqual(mapping["status"], "ready", item["headline"])
            self.assertTrue(search_queries(item), item["headline"])

    def test_generic_metadata_matches_are_rejected_as_insufficiently_specific(self):
        cases = [
            (
                {"headline": "बहरीन में अमेरिकी अर्ली-वॉर्निंग रडार पर हमला; ईरान का दावा", "detail": "ईरान की IRGC ने सिरिक में टेलीकॉम टावर पर हमले का दावा किया।"},
                {"title": "File:United States attack.jpg", "categories": []},
                {"ObjectName": {"value": "United States attack"}, "ImageDescription": {"value": "United States attack"}},
            ),
            (
                {"headline": "दिल्ली से पटना इलेक्ट्रिक कार लॉन्च", "detail": "BYD के सब-ब्रांड Denza N8 ने नई इलेक्ट्रिक SUV लॉन्च की।"},
                {"title": "File:Delhi electric vehicle charging.jpg", "categories": []},
                {"ObjectName": {"value": "Delhi electric vehicle charging"}, "ImageDescription": {"value": "Electric vehicle charging station in Delhi"}},
            ),
            (
                {"headline": "छठ पूजा पर दिल्ली ट्रैफिक पुलिस की एडवाइजरी", "detail": "दिल्ली में ट्रैफिक एडवाइजरी जारी हुई।"},
                {"title": "File:Chhath Puja in Delhi.jpg", "categories": []},
                {"ObjectName": {"value": "Chhath Puja in Delhi"}, "ImageDescription": {"value": "Chhath Puja at a Delhi ghat"}},
            ),
        ]
        for item, page, metadata in cases:
            self.assertIsNone(_relevance(item, page, metadata), item["headline"])

    def test_story_specific_metadata_matches_still_pass(self):
        cases = [
            (
                {"headline": "बहरीन में अमेरिकी अर्ली-वॉर्निंग रडार पर हमला; ईरान का दावा", "detail": "ईरान की IRGC ने सिरिक में टेलीकॉम टावर पर हमले का दावा किया।"},
                {"title": "File:Bahrain radar attack.jpg", "categories": []},
                {"ObjectName": {"value": "Bahrain early-warning radar attack"}, "ImageDescription": {"value": "Iran attack on Bahrain early-warning radar"}},
            ),
            (
                {"headline": "दिल्ली से पटना इलेक्ट्रिक कार लॉन्च", "detail": "BYD के सब-ब्रांड Denza N8 ने नई इलेक्ट्रिक SUV लॉन्च की।"},
                {"title": "File:Denza electric vehicle launch.jpg", "categories": []},
                {"ObjectName": {"value": "Denza N8 electric vehicle launch"}, "ImageDescription": {"value": "BYD Denza N8 launch"}},
            ),
            (
                {"headline": "छठ पूजा पर दिल्ली ट्रैफिक पुलिस की एडवाइजरी", "detail": "दिल्ली में ट्रैफिक एडवाइजरी जारी हुई।"},
                {"title": "File:Delhi traffic advisory.jpg", "categories": []},
                {"ObjectName": {"value": "Delhi traffic advisory"}, "ImageDescription": {"value": "Traffic advisory in Delhi for Chhath Puja"}},
            ),
        ]
        for item, page, metadata in cases:
            self.assertIsNotNone(_relevance(item, page, metadata), item["headline"])



if __name__ == "__main__":
    unittest.main()
