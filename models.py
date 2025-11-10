from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Restaurant(db.Model):
    __tablename__ = 'Restaurants'
    RestaurantID = db.Column(db.Integer, primary_key=True)
    RestaurantName = db.Column(db.String(100), nullable=False)
    Address = db.Column(db.String(255))
    Phone = db.Column(db.String(20))

class Product(db.Model):
    __tablename__ = 'Products'
    ProductID = db.Column(db.Integer, primary_key=True)
    ProductName = db.Column(db.String(100), nullable=False)

class RestaurantProduct(db.Model):
    __tablename__ = 'RestaurantProducts'
    ID = db.Column(db.Integer, primary_key=True)
    RestaurantID = db.Column(db.Integer, db.ForeignKey('Restaurants.RestaurantID'))
    ProductID = db.Column(db.Integer, db.ForeignKey('Products.ProductID'))
    Price = db.Column(db.Numeric(10,2))

class Order(db.Model):
    __tablename__ = 'Orders'
    OrderID = db.Column(db.Integer, primary_key=True)
    RestaurantID = db.Column(db.Integer, db.ForeignKey('Restaurants.RestaurantID'))
    OrderDate = db.Column(db.DateTime)
    TotalAmount = db.Column(db.Numeric(10,2))

class OrderDetail(db.Model):
    __tablename__ = 'OrderDetails'
    ID = db.Column(db.Integer, primary_key=True)
    OrderID = db.Column(db.Integer, db.ForeignKey('Orders.OrderID'))
    ProductID = db.Column(db.Integer, db.ForeignKey('Products.ProductID'))
    Quantity = db.Column(db.Integer)
    Price = db.Column(db.Numeric(10,2))
    SubTotal = db.Column(db.Numeric(10,2))
