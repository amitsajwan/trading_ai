import unittest
from pymongo import MongoClient
from mongodb_schema import setup_mongodb

class TestMongoDBSchema(unittest.TestCase):

    def setUp(self):
        # Setup MongoDB client and test database
        self.client = MongoClient("mongodb://localhost:27017/")
        self.db = self.client["test_trading_system"]

    def tearDown(self):
        # Drop the test database after each test
        self.client.drop_database("test_trading_system")

    def test_mongodb_schema_setup(self):
        # Replace the database name in the setup function
        original_db_name = "trading_system"
        setup_mongodb.__globals__["get_mongo_client"] = lambda: self.client
        setup_mongodb.__globals__["trading_system"] = "test_trading_system"

        # Run the setup function
        setup_mongodb()

        # Check if collections and indexes are created
        collections = self.db.list_collection_names()
        self.assertIn("historical_data", collections)
        self.assertIn("trade_logs", collections)

        historical_indexes = self.db["historical_data"].index_information()
        self.assertIn("timestamp_1", historical_indexes)

        trade_logs_indexes = self.db["trade_logs"].index_information()
        self.assertIn("trade_id_1", trade_logs_indexes)

if __name__ == "__main__":
    unittest.main()