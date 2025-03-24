######################################################################
# Copyright 2016, 2023 John J. Rofrano. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
######################################################################
"""
Product API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
  codecov --token=$CODECOV_TOKEN

  While debugging just these tests it's convenient to use this:
    nosetests --stop tests/test_service.py:TestProductService
"""
import os
import logging
from decimal import Decimal
from unittest import TestCase
from service import app
from service.common import status
from service.models import db, init_db, Product
from tests.factories import ProductFactory
from urllib.parse import quote_plus

# Disable all but critical errors during normal test run
# uncomment for debugging failing tests
# logging.disable(logging.CRITICAL)

# DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///../db/test.db')
DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)
BASE_URL = "/products"


######################################################################
#  T E S T   C A S E S
######################################################################
# pylint: disable=too-many-public-methods
class TestProductRoutes(TestCase):
    """Product Service tests"""


    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        # Set up the test database
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)


    @classmethod
    def tearDownClass(cls):
        """Run once after all tests"""
        db.session.close()


    def setUp(self):
        """Runs before each test"""
        self.client = app.test_client()
        db.session.query(Product).delete()  # clean up the last tests
        db.session.commit()


    def tearDown(self):
        db.session.remove()


    ############################################################
    # Utility function to bulk create products
    ############################################################
    def _create_products(self, count: int = 1) -> list:
        """Factory method to create products in bulk"""
        products = []
        for _ in range(count):
            test_product = ProductFactory()
            response = self.client.post(BASE_URL, json=test_product.serialize())
            self.assertEqual(
                response.status_code, status.HTTP_201_CREATED, "Could not create test product"
            )
            new_product = response.get_json()
            test_product.id = new_product["id"]
            products.append(test_product)
        return products


    ############################################################
    #  T E S T   C A S E S
    ############################################################
    def test_index(self):
        """It should return the index page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b"Product Catalog Administration", response.data)


    def test_health(self):
        """It should be healthy"""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data['message'], 'OK')


    # ----------------------------------------------------------
    # TEST CREATE
    # ----------------------------------------------------------
    def test_create_product(self):
        """It should Create a new Product"""
        test_product = ProductFactory()
        logging.debug("Test Product: %s", test_product.serialize())
        response = self.client.post(BASE_URL, json=test_product.serialize())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_product = response.get_json()
        self.assertEqual(new_product["name"], test_product.name)
        self.assertEqual(new_product["description"], test_product.description)
        self.assertEqual(Decimal(new_product["price"]), test_product.price)
        self.assertEqual(new_product["available"], test_product.available)
        self.assertEqual(new_product["category"], test_product.category.name)

        #
        # Uncomment this code once READ is implemented
        #

        # # Check that the location header was correct
        # response = self.client.get(location)
        # self.assertEqual(response.status_code, status.HTTP_200_OK)
        # new_product = response.get_json()
        # self.assertEqual(new_product["name"], test_product.name)
        # self.assertEqual(new_product["description"], test_product.description)
        # self.assertEqual(Decimal(new_product["price"]), test_product.price)
        # self.assertEqual(new_product["available"], test_product.available)
        # self.assertEqual(new_product["category"], test_product.category.name)


    def test_create_product_with_no_name(self):
        """It should not Create a Product without a name"""
        product = self._create_products()[0]
        new_product = product.serialize()
        del new_product["name"]
        logging.debug("Product no name: %s", new_product)
        response = self.client.post(BASE_URL, json=new_product)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def test_create_product_no_content_type(self):
        """It should not Create a Product with no Content-Type"""
        response = self.client.post(BASE_URL, data="bad data")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)


    def test_create_product_wrong_content_type(self):
        """It should not Create a Product with wrong Content-Type"""
        response = self.client.post(BASE_URL, data={}, content_type="plain/text")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)


    def test_get_product(self):
        """Get a single product"""
        test_product = self._create_products(1)[0]
        response = self.client.get(f'{BASE_URL}/{test_product.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["name"], test_product.name)


    def test_get_product_not_found(self):
        """Get a product that doesn't exist"""
        response = self.client.get(f'{BASE_URL}/999')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        data = response.get_json()
        self.assertIn("not found", data["message"])


    def test_update_product(self):
        """Update a product"""
        # Add product first
        test_product = ProductFactory()
        response = self.client.post(BASE_URL, json=test_product.serialize())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Update the product
        test_product = response.get_json()
        test_product["description"] = "New Description"
        response = self.client.put(f'{BASE_URL}/{test_product["id"]}', json=test_product)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["description"], test_product["description"])


    def test_update_product_not_found(self):
        """Update a product that doesn't exist"""
        # Add product first
        test_product = ProductFactory()
        response = self.client.post(BASE_URL, json=test_product.serialize())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Update the product
        test_product.id = 999
        response = self.client.put(f'{BASE_URL}/{test_product.id}', json=test_product.serialize())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        data = response.get_json()
        self.assertIn("not found", data["message"])


    def test_delete_product(self):
        """Delete a product"""
        # Create some products
        test_products = self._create_products(5)
        count = self.get_product_count()

        # Delete the first product
        test_product = test_products[0]
        response = self.client.delete(f'{BASE_URL}/{test_product.id}')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(response.data), 0)

        # Check that the product is gone
        response = self.client.get(f'{BASE_URL}/{test_product.id}')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        updated_count = self.get_product_count()
        self.assertEqual(updated_count, count - 1)


    def test_list_all(self):
        """List all products"""
        self._create_products(5)
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(len(data), 5)


    def test_list_by_names(self):
        """List products by name"""
        # Create some products
        test_products = self._create_products(5)
        test_name = test_products[0].name
        test_count = sum(1 for product in test_products if product.name == test_name)
        logging.debug("Found %d products with category %s", test_count, test_name)
        response = self.client.get(BASE_URL, query_string=f'name={quote_plus(test_name)}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Compare the results
        data = response.get_json()
        self.assertEqual(len(data), test_count)
        for product in data:
            self.assertEqual(product["name"], test_name)


    def test_list_by_category(self):
        """List products by category"""
        # Create some products
        test_products = self._create_products(10)
        test_category = test_products[0].category
        found = [product for product in test_products if product.category == test_category]
        found_count = len(found)
        logging.debug("Found %d products with category %s", found_count, test_category)
        response = self.client.get(BASE_URL, query_string=f'category={quote_plus(test_category.name)}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Compare the results
        data = response.get_json()
        self.assertEqual(len(data), found_count)
        for product in data:
            self.assertEqual(product["category"], test_category.name)


    def test_list_by_availability(self):
        """List products by availability"""
        test_products = self._create_products(10)
        available_test_products = [product for product in test_products if product.available == True]
        found_count = len(available_test_products)
        logging.debug("Found %d products with availability %s", found_count, available_test_products)
        response = self.client.get(BASE_URL, query_string="available=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Compare the results
        data = response.get_json()
        self.assertEqual(len(data), found_count)
        for product in data:
            self.assertEqual(product["available"], True)


    ######################################################################
    # Utility functions
    ######################################################################

    def get_product_count(self):
        """save the current number of products"""
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        # logging.debug("data = %s", data)
        return len(data)
