from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import mysql.connector
from datetime import datetime
import os
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = 'your-secret-key-123'

import os
from urllib.parse import urlparse
import mysql.connector
from mysql.connector import Error

def get_db_connection():
    connection = None
    
    # المحاولة 1: CloudClusters (المتغيرات المنفصلة)
    db_host = os.environ.get('DB_HOST')
    db_user = os.environ.get('DB_USER') 
    db_password = os.environ.get('DB_PASSWORD')
    db_name = os.environ.get('DB_NAME')
    db_port = os.environ.get('DB_PORT', '3306')
    
    if db_host and db_user and db_password:
        print(f"🔗 جرب الاتصال بـ CloudClusters: {db_host}")
        
        try:
            connection = mysql.connector.connect(
                host=db_host,
                user=db_user,
                password=db_password,
                database=db_name,
                port=int(db_port),
                ssl_disabled=True,
                connect_timeout=10,
                autocommit=True
            )
            print("✅ تم الاتصال بـ CloudClusters بنجاح!")
            return connection
        except Error as e:
            print(f"❌ فشل CloudClusters: {e}")
    
    # المحاولة 2: DATABASE_URL
    database_url = os.environ.get('DATABASE_URL')
    if database_url and 'mysql://' in database_url:
        try:
            url = urlparse(database_url)
            print(f"🔗 جرب الاتصال via DATABASE_URL: {url.hostname}")
            
            connection = mysql.connector.connect(
                host=url.hostname,
                user=url.username,
                password=url.password,
                database=url.path[1:],
                port=url.port or 3306,
                ssl_disabled=True
            )
            print("✅ تم الاتصال via DATABASE_URL بنجاح!")
            return connection
        except Error as e:
            print(f"❌ فشل DATABASE_URL: {e}")
    
    # المحاولة 3: الإعدادات المحلية
    print("🖥️  استخدام قاعدة البيانات المحلية")
    try:
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="forn",
            autocommit=True
        )
    except Error as e:
        print(f"❌ فشل الاتصال المحلي: {e}")
        raise Exception("فشل جميع محاولات الاتصال بقاعدة البيانات")

@app.route('/test-connection')
def test_connection():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # اختبار الاتصال
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        
        # اختبار الجداول
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return f"""
        <h2>✅ اختبار الاتصال ناجح!</h2>
        <p><strong>إصدار MySQL:</strong> {version[0]}</p>
        <p><strong>الجداول الموجودة:</strong> {len(tables)}</p>
        <ul>
            {''.join([f'<li>{table[0]}</li>' for table in tables])}
        </ul>
        """
        
    except Exception as e:
        return f"<h2>❌ فشل الاختبار:</h2><p>{str(e)}</p>"


# إضافة context processor لتمرير now تلقائياً لجميع القوالب
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# دالة مساعدة لتحويل Decimal إلى float
def convert_decimals(data):
    """تحويل جميع قيم Decimal في القاموس إلى float"""
    if isinstance(data, dict):
        for key, value in data.items():
            if hasattr(value, '__class__') and value.__class__.__name__ == 'Decimal':
                data[key] = float(value)
    return data




app = Flask(__name__)
app.secret_key = 'your-secret-key-123'

# إضافة فلاتر مخصصة لـ Jinja2
@app.template_filter('number_format')
def number_format(value):
    """تنسيق الأرقام بفواصل الآلاف"""
    try:
        if value is None:
            return "0"
        # تحويل إلى عدد صحيح إذا كان عشرياً بدون كسور
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return f"{value:,}"
    except (ValueError, TypeError):
        return str(value)

@app.template_filter('currency_format')
def currency_format(value):
    """تنسيق العملة"""
    try:
        if value is None:
            return "0.00 جنيه"
        return f"{float(value):,.2f} جنيه"
    except (ValueError, TypeError):
        return "0.00 جنيه"

# الصفحة الرئيسية
@app.route('/')
def index():
    return render_template("index.html")


# عرض المطاعم مع منتجاتها
@app.route("/restaurants")
def restaurants():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # جلب المطاعم مع منتجاتها
    cursor.execute("""
        SELECT r.id, r.name, 
               GROUP_CONCAT(CONCAT(p.name, '|', p.price, '|', p.id) SEPARATOR ';;') as products
        FROM restaurants r
        LEFT JOIN products p ON r.id = p.restaurant_id
        GROUP BY r.id, r.name
        ORDER BY r.name
    """)
    restaurants = cursor.fetchall()

    # معالجة البيانات لعرضها بشكل أفضل
    for restaurant in restaurants:
        if restaurant['products']:
            products_list = []
            products_data = restaurant['products'].split(';;')
            for product_data in products_data:
                if product_data:
                    name, price, product_id = product_data.split('|')
                    products_list.append({
                        'id': product_id,
                        'name': name,
                        'price': float(price)
                    })
            restaurant['products_list'] = products_list
        else:
            restaurant['products_list'] = []

    cursor.close()
    conn.close()

    return render_template("restaurants.html", restaurants=restaurants)

# روت لتعديل المطعم
@app.route("/edit_restaurant/<int:restaurant_id>", methods=["GET", "POST"])
def edit_restaurant(restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["name"]
        product_names = request.form.getlist("product_name[]")
        product_prices = request.form.getlist("product_price[]")
        product_ids = request.form.getlist("product_id[]")

        try:
            # تحديث اسم المطعم
            cursor.execute("UPDATE restaurants SET name = %s WHERE id = %s", (name, restaurant_id))

            # تحديث المنتجات الحالية وإضافة الجديدة
            for i in range(len(product_names)):
                if product_names[i].strip() and product_prices[i].strip():
                    if i < len(product_ids) and product_ids[i]:  # منتج موجود
                        cursor.execute(
                            "UPDATE products SET name = %s, price = %s WHERE id = %s",
                            (product_names[i].strip(), float(product_prices[i]), product_ids[i])
                        )
                    else:  # منتج جديد
                        cursor.execute(
                            "INSERT INTO products (restaurant_id, name, price) VALUES (%s, %s, %s)",
                            (restaurant_id, product_names[i].strip(), float(product_prices[i]))
                        )

            conn.commit()
            flash("تم تحديث المطعم بنجاح!", "success")
            return redirect(url_for("restaurants"))

        except Exception as e:
            conn.rollback()
            flash(f"حدث خطأ أثناء التحديث: {str(e)}", "error")

    # جلب بيانات المطعم الحالية
    cursor.execute("SELECT * FROM restaurants WHERE id = %s", (restaurant_id,))
    restaurant = cursor.fetchone()

    cursor.execute("SELECT * FROM products WHERE restaurant_id = %s", (restaurant_id,))
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("edit_restaurant.html", restaurant=restaurant, products=products)

# روت لحذف منتج
@app.route("/delete_product/<int:product_id>")
def delete_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
        conn.commit()
        flash("تم حذف المنتج بنجاح!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"حدث خطأ أثناء الحذف: {str(e)}", "error")

    cursor.close()
    conn.close()
    return redirect(request.referrer or url_for('restaurants'))

@app.route("/add_restaurant", methods=["GET", "POST"])
def add_restaurant():
    if request.method == "POST":
        name = request.form["name"]
        product_names = request.form.getlist("product_name[]")
        product_prices = request.form.getlist("product_price[]")

        # التحقق من صحة البيانات
        if not name.strip():
            flash("يرجى إدخال اسم المطعم", "error")
            return render_template("add_restaurant.html")

        # التحقق من وجود منتجات على الأقل
        valid_products = []
        for i in range(len(product_names)):
            product_name = product_names[i].strip()
            product_price = product_prices[i].strip()

            if product_name and product_price:
                try:
                    price = float(product_price)
                    if price >= 0:
                        valid_products.append((product_name, price))
                except ValueError:
                    flash("يرجى إدخال أسعار صحيحة للمنتجات", "error")
                    return render_template("add_restaurant.html")

        if not valid_products:
            flash("يرجى إدخال منتج واحد على الأقل", "error")
            return render_template("add_restaurant.html")

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # إضافة المطعم
            cursor.execute("INSERT INTO restaurants (name) VALUES (%s)", (name,))
            restaurant_id = cursor.lastrowid

            # إضافة المنتجات
            for product_name, product_price in valid_products:
                cursor.execute(
                    "INSERT INTO products (restaurant_id, name, price) VALUES (%s, %s, %s)",
                    (restaurant_id, product_name, product_price)
                )

            conn.commit()
            flash("تم إضافة المطعم والمنتجات بنجاح!", "success")

        except Exception as e:
            conn.rollback()
            flash(f"حدث خطأ أثناء الإضافة: {str(e)}", "error")
            return render_template("add_restaurant.html")

        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("restaurants"))

    return render_template("add_restaurant.html")


# روت لجلب المنتجات بناءً على المطعم المحدد
@app.route('/get_products/<int:restaurant_id>')
def get_products(restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, name, price FROM products WHERE restaurant_id = %s", (restaurant_id,))
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(products)


# إضافة طلب
@app.route('/add_order', methods=['GET', 'POST'])
def add_order():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # جلب أسماء المطاعم
    cursor.execute("SELECT id, name FROM restaurants")
    restaurants = cursor.fetchall()

    if request.method == 'POST':
        restaurant_id = request.form['restaurant_id']
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        order_date = request.form.get('order_date')

        # التحقق من البيانات
        if not restaurant_id:
            flash("يرجى اختيار المطعم", "error")
            return redirect(url_for('add_order'))

        valid_items = []
        total_price = 0

        for i in range(len(product_ids)):
            if product_ids[i] and quantities[i]:
                try:
                    # جلب سعر المنتج
                    cursor.execute("SELECT price FROM products WHERE id = %s", (product_ids[i],))
                    product = cursor.fetchone()
                    if product:
                        quantity = int(quantities[i])
                        price = float(product['price'])
                        subtotal = quantity * price
                        total_price += subtotal

                        valid_items.append({
                            'product_id': product_ids[i],
                            'quantity': quantity,
                            'price': price,
                            'subtotal': subtotal
                        })
                except (ValueError, TypeError):
                    continue

        if not valid_items:
            flash("يرجى إضافة منتج واحد على الأقل", "error")
            return redirect(url_for('add_order'))

        try:
            # إضافة طلب منفصل لكل منتج
            for item in valid_items:
                cursor.execute("""
                    INSERT INTO orders (restaurant_id, product_id, quantity, total_price, order_date) 
                    VALUES (%s, %s, %s, %s, %s)
                """, (restaurant_id, item['product_id'], item['quantity'], item['subtotal'], order_date))

            conn.commit()
            flash(f"تم إضافة {len(valid_items)} طلب بنجاح! إجمالي المبلغ: {total_price} جنيه", "success")

        except Exception as e:
            conn.rollback()
            flash(f"حدث خطأ أثناء إضافة الطلب: {str(e)}", "error")

        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('orders'))

    conn.close()
    return render_template('add_order.html', restaurants=restaurants)


@app.route('/orders', methods=['GET', 'POST'])
def orders():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # جلب المطاعم للفلترة
    cursor.execute("SELECT id, name FROM restaurants")
    restaurants = cursor.fetchall()

    # بناء الاستعلام الأساسي
    query = """
        SELECT 
            r.id as restaurant_id,
            r.name AS restaurant_name,
            DATE(o.order_date) AS order_date,
            GROUP_CONCAT(CONCAT(p.name, ' (', o.quantity, ')') SEPARATOR ' - ') AS products_details,
            SUM(o.quantity) AS total_quantity,
            SUM(o.total_price) AS total_amount,
            COUNT(o.id) AS orders_count
        FROM orders o
        JOIN restaurants r ON o.restaurant_id = r.id
        JOIN products p ON o.product_id = p.id
        WHERE 1=1
    """
    params = []

    selected_restaurant = None
    selected_date = None

    if request.method == 'POST':
        selected_restaurant = request.form.get('restaurant_id')
        selected_date = request.form.get('order_date')

        if selected_restaurant:
            query += " AND o.restaurant_id = %s"
            params.append(selected_restaurant)

        if selected_date:
            query += " AND DATE(o.order_date) = %s"
            params.append(selected_date)

    query += " GROUP BY r.id, r.name, DATE(o.order_date) ORDER BY order_date DESC, r.name"

    cursor.execute(query, tuple(params))
    orders_data = cursor.fetchall()

    # تحويل جميع القيم العددية إلى float لتجنب مشاكل الأنواع
    for order in orders_data:
        order['total_amount'] = float(order['total_amount']) if order['total_amount'] else 0.0
        order['total_quantity'] = int(order['total_quantity']) if order['total_quantity'] else 0
        order['restaurant_id'] = int(order['restaurant_id']) if order['restaurant_id'] else 0

    conn.close()

    return render_template(
        'orders.html',
        orders=orders_data,
        restaurants=restaurants,
        selected_restaurant=selected_restaurant,
        selected_date=selected_date
    )

# إضافة روت للإحصائيات
@app.route('/api/stats')
def get_stats():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # عدد المطاعم
    cursor.execute("SELECT COUNT(*) as count FROM restaurants")
    restaurants_count = cursor.fetchone()['count']

    # عدد الطلبات
    cursor.execute("SELECT COUNT(*) as count FROM orders")
    orders_count = cursor.fetchone()['count']

    # عدد المنتجات
    cursor.execute("SELECT COUNT(*) as count FROM products")
    products_count = cursor.fetchone()['count']

    # طلبات اليوم
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*) as count FROM orders WHERE DATE(order_date) = %s", (today,))
    today_orders = cursor.fetchone()['count']

    cursor.close()
    conn.close()

    return jsonify({
        'restaurants': restaurants_count,
        'orders': orders_count,
        'products': products_count,
        'today_orders': today_orders
    })







# 📊 روت لعرض وإضافة المدفوعات
@app.route('/payments/<int:restaurant_id>', methods=['GET', 'POST'])
def restaurant_payments(restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # جلب بيانات المطعم
    cursor.execute("SELECT * FROM restaurants WHERE id = %s", (restaurant_id,))
    restaurant = cursor.fetchone()

    if request.method == 'POST':
        # معالجة إضافة دفعة جديدة
        amount_paid = float(request.form['amount_paid'])
        payment_method = request.form['payment_method']
        notes = request.form.get('notes', '')

        try:
            # حساب الإجمالي المستحق من الطلبات
            cursor.execute("""
                SELECT COALESCE(SUM(total_price), 0) as total_due 
                FROM orders 
                WHERE restaurant_id = %s
            """, (restaurant_id,))
            total_due = cursor.fetchone()['total_due']

            # حساب إجمالي المدفوعات السابقة
            cursor.execute("""
                SELECT COALESCE(SUM(amount_paid), 0) as total_paid 
                FROM payments 
                WHERE restaurant_id = %s
            """, (restaurant_id,))
            total_paid = cursor.fetchone()['total_paid']

            # حساب المتبقي بعد الدفعة الجديدة
            remaining_balance = total_due - (total_paid + amount_paid)

            # إنشاء رقم إيصال تلقائي
            receipt_number = f"PMT-{datetime.now().strftime('%Y%m%d')}-{restaurant_id:03d}"

            # إضافة الدفعة الجديدة
            cursor.execute("""
                INSERT INTO payments (restaurant_id, amount_paid, payment_method, remaining_balance, notes, receipt_number)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (restaurant_id, amount_paid, payment_method, remaining_balance, notes, receipt_number))

            conn.commit()
            flash(f"تم تسجيل الدفعة بنجاح! رقم الإيصال: {receipt_number}", "success")

        except Exception as e:
            conn.rollback()
            flash(f"حدث خطأ أثناء تسجيل الدفعة: {str(e)}", "error")

    # جلب سجل المدفوعات
    cursor.execute("""
        SELECT * FROM payments 
        WHERE restaurant_id = %s 
        ORDER BY payment_date DESC
    """, (restaurant_id,))
    payments = cursor.fetchall()

    # حساب الإحصائيات الحالية
    cursor.execute("""
        SELECT 
            COALESCE(SUM(total_price), 0) as total_due,
            COALESCE(SUM(amount_paid), 0) as total_paid
        FROM orders 
        LEFT JOIN payments ON orders.restaurant_id = payments.restaurant_id
        WHERE orders.restaurant_id = %s
    """, (restaurant_id,))
    stats = cursor.fetchone()

    remaining_balance = stats['total_due'] - stats['total_paid']

    cursor.close()
    conn.close()

    return render_template('restaurant_payments.html',
                           restaurant=restaurant,
                           payments=payments,
                           stats=stats,
                           remaining_balance=remaining_balance)


@app.route('/add_payment/<int:restaurant_id>', methods=['POST'])
def add_payment(restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        amount_paid = float(request.form['amount_paid'])
        payment_method = request.form['payment_method']
        notes = request.form.get('notes', '')

        # حساب المبالغ الحالية مع تحويل الأنواع
        cursor.execute("SELECT COALESCE(SUM(total_price), 0) as total_due FROM orders WHERE restaurant_id = %s",
                       (restaurant_id,))
        total_due_result = cursor.fetchone()
        total_due = float(total_due_result['total_due'])

        cursor.execute("SELECT COALESCE(SUM(amount_paid), 0) as total_paid FROM payments WHERE restaurant_id = %s",
                       (restaurant_id,))
        total_paid_result = cursor.fetchone()
        total_paid = float(total_paid_result['total_paid'])

        remaining_balance = total_due - (total_paid + amount_paid)

        # رقم إيصال تلقائي
        receipt_number = f"PMT-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{restaurant_id:03d}"

        cursor.execute("""
            INSERT INTO payments (restaurant_id, amount_paid, payment_method, remaining_balance, notes, receipt_number)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (restaurant_id, amount_paid, payment_method, remaining_balance, notes, receipt_number))

        conn.commit()

        return jsonify({
            'success': True,
            'message': f'تم تسجيل الدفعة بنجاح! رقم الإيصال: {receipt_number}',
            'receipt_number': receipt_number,
            'remaining_balance': remaining_balance
        })

    except Exception as e:
        conn.rollback()
        return jsonify({
            'success': False,
            'message': f'حدث خطأ: {str(e)}'
        })

    finally:
        cursor.close()
        conn.close()


# 📈 روت كشف حساب المطعم مع الفلترة
@app.route('/account_statement/<int:restaurant_id>', methods=['GET', 'POST'])
def account_statement(restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # بيانات المطعم
        cursor.execute("SELECT * FROM restaurants WHERE id = %s", (restaurant_id,))
        restaurant = cursor.fetchone()

        if not restaurant:
            flash("المطعم غير موجود", "error")
            return redirect(url_for('orders'))

        # معالجة الفلترة
        start_date = request.form.get('start_date', '')
        end_date = request.form.get('end_date', '')
        filter_type = request.form.get('filter_type', 'all')  # all, orders, payments

        # بناء استعلام الطلبات مع الفلترة
        orders_query = """
            SELECT o.*, p.name as product_name, p.price as unit_price
            FROM orders o 
            JOIN products p ON o.product_id = p.id 
            WHERE o.restaurant_id = %s
        """
        orders_params = [restaurant_id]

        # بناء استعلام المدفوعات مع الفلترة
        payments_query = """
            SELECT * FROM payments 
            WHERE restaurant_id = %s
        """
        payments_params = [restaurant_id]

        # تطبيق فلترة التاريخ
        if start_date:
            orders_query += " AND DATE(o.order_date) >= %s"
            orders_params.append(start_date)
            payments_query += " AND DATE(payment_date) >= %s"
            payments_params.append(start_date)

        if end_date:
            orders_query += " AND DATE(o.order_date) <= %s"
            orders_params.append(end_date)
            payments_query += " AND DATE(payment_date) <= %s"
            payments_params.append(end_date)

        # إضافة الترتيب والحد
        orders_query += " ORDER BY o.order_date DESC LIMIT 100"
        payments_query += " ORDER BY payment_date DESC LIMIT 100"

        # تنفيذ الاستعلامات
        cursor.execute(orders_query, tuple(orders_params))
        orders = cursor.fetchall()

        cursor.execute(payments_query, tuple(payments_params))
        payments = cursor.fetchall()

        # 🔧 الإحصائيات مع الفلترة
        # إجمالي الطلبات المفلترة
        total_orders_query = "SELECT COALESCE(SUM(total_price), 0) as total_orders FROM orders WHERE restaurant_id = %s"
        total_orders_params = [restaurant_id]

        if start_date:
            total_orders_query += " AND DATE(order_date) >= %s"
            total_orders_params.append(start_date)
        if end_date:
            total_orders_query += " AND DATE(order_date) <= %s"
            total_orders_params.append(end_date)

        cursor.execute(total_orders_query, tuple(total_orders_params))
        total_orders_result = cursor.fetchone()
        total_orders = float(total_orders_result['total_orders'])

        # إجمالي المدفوعات المفلترة
        total_payments_query = "SELECT COALESCE(SUM(amount_paid), 0) as total_payments FROM payments WHERE restaurant_id = %s"
        total_payments_params = [restaurant_id]

        if start_date:
            total_payments_query += " AND DATE(payment_date) >= %s"
            total_payments_params.append(start_date)
        if end_date:
            total_payments_query += " AND DATE(payment_date) <= %s"
            total_payments_params.append(end_date)

        cursor.execute(total_payments_query, tuple(total_payments_params))
        total_payments_result = cursor.fetchone()
        total_payments = float(total_payments_result['total_payments'])

        # الرصيد الحالي
        balance = total_orders - total_payments

        # عدد الطلبات والمدفوعات المفلترة
        orders_count = len(orders)
        payments_count = len(payments)

        # آخر دفعة
        last_payment = payments[0] if payments else None

        print(f"فلترة كشف الحساب - من: {start_date}, إلى: {end_date}")
        print(f"الطلبات: {orders_count}, المدفوعات: {payments_count}")

        return render_template('account_statement.html',
                               restaurant=restaurant,
                               orders=orders,
                               payments=payments,
                               total_orders=total_orders,
                               total_payments=total_payments,
                               balance=balance,
                               orders_count=orders_count,
                               payments_count=payments_count,
                               last_payment=last_payment,
                               start_date=start_date,
                               end_date=end_date,
                               filter_type=filter_type,
                               now=datetime.now())

    except Exception as e:
        print(f"خطأ في كشف الحساب: {str(e)}")
        flash(f"حدث خطأ: {str(e)}", "error")
        return redirect(url_for('orders'))
    finally:
        cursor.close()
        conn.close()


# 📊 روت تقارير التحصيل الشاملة - الإصدار المصحح
@app.route('/payment_reports', methods=['GET', 'POST'])
def payment_reports():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # معالجة الفلترة
        start_date = request.form.get('start_date', '')
        end_date = request.form.get('end_date', '')
        report_type = request.form.get('report_type', 'summary')

        # 🔧 الإحصائيات العامة المصححة
        # إجمالي المدفوعات مع الفلترة
        total_payments_query = "SELECT COALESCE(SUM(amount_paid), 0) as total_payments FROM payments WHERE 1=1"
        total_payments_params = []

        if start_date:
            total_payments_query += " AND DATE(payment_date) >= %s"
            total_payments_params.append(start_date)

        if end_date:
            total_payments_query += " AND DATE(payment_date) <= %s"
            total_payments_params.append(end_date)

        cursor.execute(total_payments_query, tuple(total_payments_params))
        total_payments_result = cursor.fetchone()
        total_payments = float(total_payments_result['total_payments'])

        # إجمالي الطلبات مع الفلترة
        total_orders_query = "SELECT COALESCE(SUM(total_price), 0) as total_orders FROM orders WHERE 1=1"
        total_orders_params = []

        if start_date:
            total_orders_query += " AND DATE(order_date) >= %s"
            total_orders_params.append(start_date)

        if end_date:
            total_orders_query += " AND DATE(order_date) <= %s"
            total_orders_params.append(end_date)

        cursor.execute(total_orders_query, tuple(total_orders_params))
        total_orders_result = cursor.fetchone()
        total_orders = float(total_orders_result['total_orders'])

        # 🔧 إحصائيات المطاعم المصححة
        restaurants_query = """
            SELECT 
                r.id,
                r.name,
                COALESCE(SUM(o.total_price), 0) as total_orders,
                COALESCE(SUM(p.amount_paid), 0) as total_paid,
                (COALESCE(SUM(o.total_price), 0) - COALESCE(SUM(p.amount_paid), 0)) as balance
            FROM restaurants r
            LEFT JOIN orders o ON r.id = o.restaurant_id
            LEFT JOIN payments p ON r.id = p.restaurant_id
            WHERE 1=1
        """
        restaurants_params = []

        if start_date:
            restaurants_query += " AND (o.order_date IS NULL OR DATE(o.order_date) >= %s)"
            restaurants_params.append(start_date)
            restaurants_query += " AND (p.payment_date IS NULL OR DATE(p.payment_date) >= %s)"
            restaurants_params.append(start_date)

        if end_date:
            restaurants_query += " AND (o.order_date IS NULL OR DATE(o.order_date) <= %s)"
            restaurants_params.append(end_date)
            restaurants_query += " AND (p.payment_date IS NULL OR DATE(p.payment_date) <= %s)"
            restaurants_params.append(end_date)

        restaurants_query += " GROUP BY r.id, r.name ORDER BY balance DESC"

        cursor.execute(restaurants_query, tuple(restaurants_params))
        restaurants_stats = cursor.fetchall()

        # 🔧 جلب عدد الطلبات والمدفوعات لكل مطعم بشكل منفصل
        for restaurant in restaurants_stats:
            # عدد الطلبات
            orders_count_query = "SELECT COUNT(*) as count FROM orders WHERE restaurant_id = %s"
            orders_count_params = [restaurant['id']]

            if start_date:
                orders_count_query += " AND DATE(order_date) >= %s"
                orders_count_params.append(start_date)
            if end_date:
                orders_count_query += " AND DATE(order_date) <= %s"
                orders_count_params.append(end_date)

            cursor.execute(orders_count_query, tuple(orders_count_params))
            orders_count_result = cursor.fetchone()
            restaurant['orders_count'] = orders_count_result['count']

            # عدد المدفوعات
            payments_count_query = "SELECT COUNT(*) as count FROM payments WHERE restaurant_id = %s"
            payments_count_params = [restaurant['id']]

            if start_date:
                payments_count_query += " AND DATE(payment_date) >= %s"
                payments_count_params.append(start_date)
            if end_date:
                payments_count_query += " AND DATE(payment_date) <= %s"
                payments_count_params.append(end_date)

            cursor.execute(payments_count_query, tuple(payments_count_params))
            payments_count_result = cursor.fetchone()
            restaurant['payments_count'] = payments_count_result['count']

            # تحويل الأنواع
            restaurant['total_orders'] = float(restaurant['total_orders'])
            restaurant['total_paid'] = float(restaurant['total_paid'])
            restaurant['balance'] = float(restaurant['balance'])

        # 🔧 المطاعم المتأخرة (أعلى رصيد)
        late_restaurants = [r for r in restaurants_stats if r['balance'] > 0]
        late_restaurants.sort(key=lambda x: x['balance'], reverse=True)

        # 🔧 المطاعم الأعلى تحصيلاً
        top_restaurants_query = """
            SELECT 
                r.name,
                SUM(p.amount_paid) as total_paid,
                COUNT(p.id) as payments_count
            FROM restaurants r
            JOIN payments p ON r.id = p.restaurant_id
            WHERE 1=1
        """
        top_params = []

        if start_date:
            top_restaurants_query += " AND DATE(p.payment_date) >= %s"
            top_params.append(start_date)

        if end_date:
            top_restaurants_query += " AND DATE(p.payment_date) <= %s"
            top_params.append(end_date)

        top_restaurants_query += " GROUP BY r.id, r.name ORDER BY total_paid DESC LIMIT 5"

        cursor.execute(top_restaurants_query, tuple(top_params))
        top_restaurants = cursor.fetchall()

        # 🔧 المدفوعات اليومية
        daily_payments_query = """
            SELECT 
                DATE(payment_date) as payment_day,
                SUM(amount_paid) as daily_total,
                COUNT(*) as payments_count
            FROM payments 
            WHERE 1=1
        """
        daily_params = []

        if start_date:
            daily_payments_query += " AND DATE(payment_date) >= %s"
            daily_params.append(start_date)

        if end_date:
            daily_payments_query += " AND DATE(payment_date) <= %s"
            daily_params.append(end_date)

        daily_payments_query += " GROUP BY DATE(payment_date) ORDER BY payment_day DESC LIMIT 7"

        cursor.execute(daily_payments_query, tuple(daily_params))
        daily_payments = cursor.fetchall()

        # طباعة البيانات للتdebug
        print("=" * 50)
        print("تقارير التحصيل - البيانات المصححة")
        print("=" * 50)
        print(f"الفترة: {start_date} إلى {end_date}")
        print(f"إجمالي المدفوعات: {total_payments}")
        print(f"إجمالي الطلبات: {total_orders}")
        print(f"عدد المطاعم: {len(restaurants_stats)}")
        print(f"المطاعم المتأخرة: {len(late_restaurants)}")

        for i, restaurant in enumerate(restaurants_stats[:3]):  # عرض أول 3 مطاعم للتdebug
            print(f"المطعم {i + 1}: {restaurant['name']}")
            print(f"  - الطلبات: {restaurant['total_orders']} (عدد: {restaurant['orders_count']})")
            print(f"  - المدفوعات: {restaurant['total_paid']} (عدد: {restaurant['payments_count']})")
            print(f"  - الرصيد: {restaurant['balance']}")

        return render_template('payment_reports.html',
                               total_payments=total_payments,
                               total_orders=total_orders,
                               restaurants_stats=restaurants_stats,
                               daily_payments=daily_payments,
                               top_restaurants=top_restaurants,
                               late_restaurants=late_restaurants,
                               start_date=start_date,
                               end_date=end_date,
                               report_type=report_type,
                               now=datetime.now())

    except Exception as e:
        print(f"خطأ في تقارير التحصيل: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"حدث خطأ في إنشاء التقرير: {str(e)}", "error")
        return redirect(url_for('orders'))
    finally:
        cursor.close()
        conn.close()

# 📤 روت تصدير التقارير
@app.route('/export_payment_reports')
def export_payment_reports():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # جلب البيانات
        cursor.execute("""
            SELECT 
                r.name as restaurant_name,
                COALESCE(SUM(o.total_price), 0) as total_orders,
                COALESCE(SUM(p.amount_paid), 0) as total_paid,
                (COALESCE(SUM(o.total_price), 0) - COALESCE(SUM(p.amount_paid), 0)) as balance
            FROM restaurants r
            LEFT JOIN orders o ON r.id = o.restaurant_id
            LEFT JOIN payments p ON r.id = p.restaurant_id
            GROUP BY r.id, r.name
            ORDER BY balance DESC
        """)
        data = cursor.fetchall()

        # إنشاء CSV
        import csv
        from io import StringIO
        from flask import Response

        output = StringIO()
        writer = csv.writer(output)

        # كتابة headers
        writer.writerow(['المطعم', 'إجمالي الطلبات', 'إجمالي المدفوعات', 'الرصيد', 'تاريخ التصدير'])

        # كتابة البيانات
        for row in data:
            writer.writerow([
                row['restaurant_name'],
                f"{float(row['total_orders']):.2f}",
                f"{float(row['total_paid']):.2f}",
                f"{float(row['balance']):.2f}",
                datetime.now().strftime('%Y-%m-%d %H:%M')
            ])

        output.seek(0)

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=payment_reports.csv"}
        )

    except Exception as e:
        flash(f"حدث خطأ في التصدير: {str(e)}", "error")
        return redirect(url_for('payment_reports'))
    finally:
        cursor.close()
        conn.close()


# 🔔 روت إدارة إشعارات المدفوعات - الإصدار المصحح
@app.route('/payment_reminders', methods=['GET', 'POST'])
def payment_reminders():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        if request.method == 'POST':
            action = request.form.get('action')

            if action == 'add_reminder':
                # إضافة تذكير جديد
                restaurant_id = request.form['restaurant_id']
                reminder_date = request.form['reminder_date']
                amount_due = float(request.form['amount_due'])
                notes = request.form.get('notes', '')

                cursor.execute("""
                    INSERT INTO payment_reminders (restaurant_id, reminder_date, amount_due, notes, status)
                    VALUES (%s, %s, %s, %s, 'معلقة')
                """, (restaurant_id, reminder_date, amount_due, notes))

                conn.commit()
                flash("تم إضافة تذكير الدفع بنجاح!", "success")

            elif action == 'update_status':
                # تحديث حالة التذكير
                reminder_id = request.form['reminder_id']
                new_status = request.form['new_status']

                cursor.execute("""
                    UPDATE payment_reminders 
                    SET status = %s 
                    WHERE id = %s
                """, (new_status, reminder_id))

                conn.commit()
                flash("تم تحديث حالة التذكير بنجاح!", "success")

            elif action == 'generate_auto_reminders':
                # إنشاء إشعارات تلقائية للمطاعم المتأخرة
                auto_reminders_count = generate_auto_reminders()
                flash(f"تم إنشاء {auto_reminders_count} إشعار تلقائي", "success")

        # 🔧 تصحيح الاستعلام - إزالة created_at غير الموجود
        cursor.execute("""
            SELECT 
                pr.*,
                r.name as restaurant_name
            FROM payment_reminders pr
            JOIN restaurants r ON pr.restaurant_id = r.id
            ORDER BY 
                CASE WHEN pr.status = 'معلقة' THEN 1 ELSE 2 END,
                pr.reminder_date ASC
                -- تم إزالة pr.created_at لأنه غير موجود
        """)
        reminders = cursor.fetchall()

        # جلب المطاعم للقائمة المنسدلة
        cursor.execute("""
            SELECT r.id, r.name,
                   (COALESCE(SUM(o.total_price), 0) - COALESCE(SUM(p.amount_paid), 0)) as balance
            FROM restaurants r
            LEFT JOIN orders o ON r.id = o.restaurant_id
            LEFT JOIN payments p ON r.id = p.restaurant_id
            GROUP BY r.id, r.name
            HAVING balance > 0
            ORDER BY balance DESC
        """)
        restaurants = cursor.fetchall()

        # 🔧 إحصائيات الإشعارات المصححة
        pending_count = 0
        completed_count = 0
        overdue_count = 0

        for reminder in reminders:
            if reminder['status'] == 'معلقة':
                pending_count += 1
                # التحقق إذا كان التذكير منتهي الصلاحية
                if reminder['reminder_date'] < datetime.now().date():
                    overdue_count += 1
            elif reminder['status'] == 'مكتملة':
                completed_count += 1

        total_count = len(reminders)

        print(f"إحصائيات الإشعارات:")
        print(f"معلقة: {pending_count}, مكتملة: {completed_count}, منتهية: {overdue_count}, الإجمالي: {total_count}")

        return render_template('payment_reminders.html',
                               reminders=reminders,
                               restaurants=restaurants,
                               pending_count=pending_count,
                               completed_count=completed_count,
                               overdue_count=overdue_count,
                               total_count=total_count,
                               now=datetime.now())

    except Exception as e:
        print(f"خطأ في إدارة الإشعارات: {str(e)}")
        flash(f"حدث خطأ: {str(e)}", "error")
        return redirect(url_for('payment_reminders'))
    finally:
        cursor.close()
        conn.close()


# 🔔 دالة إنشاء الإشعارات التلقائية
def generate_auto_reminders():
    """
    إنشاء إشعارات تلقائية للمطاعم المتأخرة في السداد
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # جلب المطاعم التي لديها مدفوعات متأخرة
        cursor.execute("""
            SELECT 
                r.id as restaurant_id,
                r.name as restaurant_name,
                (COALESCE(SUM(o.total_price), 0) - COALESCE(SUM(p.amount_paid), 0)) as overdue_amount,
                MAX(o.order_date) as last_order_date
            FROM restaurants r
            LEFT JOIN orders o ON r.id = o.restaurant_id
            LEFT JOIN payments p ON r.id = p.restaurant_id
            GROUP BY r.id, r.name
            HAVING overdue_amount > 0
            AND NOT EXISTS (
                SELECT 1 FROM payment_reminders pr 
                WHERE pr.restaurant_id = r.id 
                AND pr.status = 'معلقة'
                AND DATE(pr.created_at) = CURDATE()
            )
        """)

        overdue_restaurants = cursor.fetchall()
        reminders_created = 0

        # إنشاء إشعار لكل مطعم متأخر
        for restaurant in overdue_restaurants:
            reminder_date = datetime.now().date()
            notes = f"تذكير تلقائي - متأخرات بقيمة: {restaurant['overdue_amount']:.2f} ريال"

            cursor.execute("""
                INSERT INTO payment_reminders 
                (restaurant_id, reminder_date, amount_due, notes, status, is_auto_generated)
                VALUES (%s, %s, %s, %s, 'معلقة', 1)
            """, (restaurant['restaurant_id'], reminder_date, restaurant['overdue_amount'], notes))

            reminders_created += 1

        conn.commit()
        return reminders_created

    except Exception as e:
        print(f"خطأ في إنشاء الإشعارات التلقائية: {str(e)}")
        conn.rollback()
        return 0
    finally:
        cursor.close()
        conn.close()
# ✅ روت تحديث حالة الإشعار
@app.route('/update_reminder_status/<int:reminder_id>')
def update_reminder_status(reminder_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE payment_reminders 
            SET status = 'مكتملة' 
            WHERE id = %s
        """, (reminder_id,))

        conn.commit()
        flash("تم تحديث حالة التذكير إلى مكتمل", "success")

    except Exception as e:
        conn.rollback()
        flash(f"حدث خطأ أثناء تحديث الحالة: {str(e)}", "error")

    cursor.close()
    conn.close()
    return redirect(url_for('payment_reminders'))


# 🗑️ روت حذف إشعار
@app.route('/delete_reminder/<int:reminder_id>')
def delete_reminder(reminder_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM payment_reminders WHERE id = %s", (reminder_id,))
        conn.commit()
        flash("تم حذف التذكير بنجاح", "success")
    except Exception as e:
        conn.rollback()
        flash(f"حدث خطأ أثناء الحذف: {str(e)}", "error")

    cursor.close()
    conn.close()
    return redirect(url_for('payment_reminders'))


# 📧 روت الإشعارات التلقائية للمطاعم المتأخرة
@app.route('/auto_reminders')
def auto_reminders():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # البحث عن المطاعم المتأخرة (رصيد أكبر من 500 جنيه ولم تدفع منذ 7 أيام)
    cursor.execute("""
        SELECT 
            r.id,
            r.name,
            COALESCE(SUM(o.total_price), 0) - COALESCE(SUM(p.amount_paid), 0) as balance,
            MAX(p.payment_date) as last_payment_date
        FROM restaurants r
        LEFT JOIN orders o ON r.id = o.restaurant_id
        LEFT JOIN payments p ON r.id = p.restaurant_id
        GROUP BY r.id, r.name
        HAVING balance > 500 
        AND (last_payment_date IS NULL OR DATEDIFF(CURDATE(), last_payment_date) > 7)
    """)
    late_restaurants = cursor.fetchall()

    # إضافة إشعارات تلقائية
    for restaurant in late_restaurants:
        cursor.execute("""
            INSERT INTO payment_reminders (restaurant_id, reminder_date, amount_due, notes, status)
            VALUES (%s, %s, %s, %s, 'معلقة')
        """, (
        restaurant['id'], datetime.now().strftime('%Y-%m-%d'), restaurant['balance'], 'تذكير تلقائي - متأخر في السداد'))

    conn.commit()

    cursor.close()
    conn.close()

    flash(f"تم إنشاء {len(late_restaurants)} إشعار تلقائي للمطاعم المتأخرة", "success")
    return redirect(url_for('payment_reminders'))


# 📊 روت التقارير التفصيلية
@app.route('/detailed_payment_reports', methods=['GET', 'POST'])
def detailed_payment_reports():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # قيم افتراضية للفلاتر
    start_date = request.form.get('start_date', '')
    end_date = request.form.get('end_date', '')
    restaurant_id = request.form.get('restaurant_id', '')

    # بناء الاستعلام الديناميكي
    query = """
        SELECT 
            p.*,
            r.name as restaurant_name,
            DATE(p.payment_date) as payment_day
        FROM payments p
        JOIN restaurants r ON p.restaurant_id = r.id
        WHERE 1=1
    """
    params = []

    if start_date:
        query += " AND DATE(p.payment_date) >= %s"
        params.append(start_date)

    if end_date:
        query += " AND DATE(p.payment_date) <= %s"
        params.append(end_date)

    if restaurant_id:
        query += " AND p.restaurant_id = %s"
        params.append(restaurant_id)

    query += " ORDER BY p.payment_date DESC"

    cursor.execute(query, tuple(params))
    payments = cursor.fetchall()

    # إحصائيات التقرير
    cursor.execute("SELECT SUM(amount_paid) as total_reported FROM payments WHERE 1=1" +
                   (" AND DATE(payment_date) >= %s" if start_date else "") +
                   (" AND DATE(payment_date) <= %s" if end_date else "") +
                   (" AND restaurant_id = %s" if restaurant_id else ""),
                   tuple([p for p in params if p]))
    stats = cursor.fetchone()

    # المطاعم للقائمة المنسدلة
    cursor.execute("SELECT id, name FROM restaurants ORDER BY name")
    restaurants = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('detailed_payment_reports.html',
                           payments=payments,
                           stats=stats,
                           restaurants=restaurants,
                           start_date=start_date,
                           end_date=end_date,
                           restaurant_id=restaurant_id)


# 📈 روت لوحة تحكم المدفوعات
@app.route('/payment_dashboard')
def payment_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # إحصائيات سريعة
    cursor.execute("SELECT COUNT(*) as total_restaurants FROM restaurants")
    total_restaurants = cursor.fetchone()['total_restaurants']

    cursor.execute("SELECT SUM(amount_paid) as total_payments FROM payments")
    total_payments = cursor.fetchone()['total_payments'] or 0

    # مدفوعات اليوم
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT SUM(amount_paid) as today_payments FROM payments WHERE DATE(payment_date) = %s", (today,))
    today_payments = cursor.fetchone()['today_payments'] or 0

    # المطاعم المتأخرة
    cursor.execute("""
        SELECT COUNT(*) as late_restaurants
        FROM (
            SELECT r.id
            FROM restaurants r
            LEFT JOIN orders o ON r.id = o.restaurant_id
            LEFT JOIN payments p ON r.id = p.restaurant_id
            GROUP BY r.id
            HAVING COALESCE(SUM(o.total_price), 0) - COALESCE(SUM(p.amount_paid), 0) > 1000
        ) as late
    """)
    late_restaurants = cursor.fetchone()['late_restaurants']

    # آخر المدفوعات
    cursor.execute("""
        SELECT p.*, r.name as restaurant_name
        FROM payments p
        JOIN restaurants r ON p.restaurant_id = r.id
        ORDER BY p.payment_date DESC
        LIMIT 10
    """)
    recent_payments = cursor.fetchall()

    # المطاعم الأعلى تحصيلاً
    cursor.execute("""
        SELECT r.name, SUM(p.amount_paid) as total_paid
        FROM restaurants r
        JOIN payments p ON r.id = p.restaurant_id
        GROUP BY r.id, r.name
        ORDER BY total_paid DESC
        LIMIT 5
    """)
    top_restaurants = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('payment_dashboard.html',
                           total_restaurants=total_restaurants,
                           total_payments=total_payments,
                           today_payments=today_payments,
                           late_restaurants=late_restaurants,
                           recent_payments=recent_payments,
                           top_restaurants=top_restaurants)


# 🖨️ روت طباعة إيصال
@app.route('/print_receipt/<int:payment_id>')
def print_receipt(payment_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT p.*, r.name as restaurant_name, r.phone, r.address
        FROM payments p
        JOIN restaurants r ON p.restaurant_id = r.id
        WHERE p.id = %s
    """, (payment_id,))
    payment = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template('print_receipt.html', payment=payment)


# 📤 روت تصدير البيانات
@app.route('/export_payments')
def export_payments():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT p.*, r.name as restaurant_name
        FROM payments p
        JOIN restaurants r ON p.restaurant_id = r.id
        ORDER BY p.payment_date DESC
    """)
    payments = cursor.fetchall()

    cursor.close()
    conn.close()

    # إنشاء CSV
    import csv
    from io import StringIO
    from flask import Response

    output = StringIO()
    writer = csv.writer(output)

    # كتابة headers
    writer.writerow(['رقم الإيصال', 'المطعم', 'المبلغ', 'طريقة الدفع', 'التاريخ', 'المتبقي', 'ملاحظات'])

    # كتابة البيانات
    for payment in payments:
        writer.writerow([
            payment['receipt_number'],
            payment['restaurant_name'],
            payment['amount_paid'],
            payment['payment_method'],
            payment['payment_date'].strftime('%Y-%m-%d %H:%M'),
            payment['remaining_balance'],
            payment['notes'] or ''
        ])

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=payments_export.csv"}
    )


@app.route('/api/restaurant_stats/<int:restaurant_id>')
def api_restaurant_stats(restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # جلب إجمالي الطلبات مع تحويل النوع
        cursor.execute("SELECT COALESCE(SUM(total_price), 0) as total_due FROM orders WHERE restaurant_id = %s",
                       (restaurant_id,))
        total_due_result = cursor.fetchone()
        total_due = float(total_due_result['total_due'])

        # جلب إجمالي المدفوعات مع تحويل النوع
        cursor.execute("SELECT COALESCE(SUM(amount_paid), 0) as total_paid FROM payments WHERE restaurant_id = %s",
                       (restaurant_id,))
        total_paid_result = cursor.fetchone()
        total_paid = float(total_paid_result['total_paid'])

        # حساب المتبقي
        remaining_balance = total_due - total_paid

        return jsonify({
            'success': True,
            'total_due': total_due,
            'total_paid': total_paid,
            'remaining_balance': remaining_balance
        })

    except Exception as e:
        print(f"Error in api_restaurant_stats: {str(e)}")
        return jsonify({
            'success': False,
            'total_due': 0.0,
            'total_paid': 0.0,
            'remaining_balance': 0.0,
            'error': str(e)
        })

    finally:
        cursor.close()
        conn.close()


# 🗑️ روت حذف دفعة
@app.route('/delete_payment/<int:payment_id>')
def delete_payment(payment_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM payments WHERE id = %s", (payment_id,))
        conn.commit()
        flash("تم حذف الدفعة بنجاح", "success")
    except Exception as e:
        conn.rollback()
        flash(f"حدث خطأ أثناء الحذف: {str(e)}", "error")

    cursor.close()
    conn.close()
    return redirect(request.referrer or url_for('payment_reports'))


# 📋 إدارة العمال
@app.route('/workers', methods=['GET', 'POST'])
def workers_management():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        price_per_thousand = float(request.form['price_per_thousand'])

        try:
            cursor.execute(
                "INSERT INTO workers (name, price_per_thousand) VALUES (%s, %s)",
                (name, price_per_thousand)
            )
            conn.commit()
            flash("تم إضافة العامل بنجاح!", "success")
        except Exception as e:
            conn.rollback()
            flash(f"حدث خطأ أثناء الإضافة: {str(e)}", "error")

    # جلب جميع العمال
    cursor.execute("SELECT * FROM workers ORDER BY name")
    workers = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('workers.html', workers=workers)


# ✏️ تعديل بيانات العامل
@app.route('/edit_worker/<int:worker_id>', methods=['GET', 'POST'])
def edit_worker(worker_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        price_per_thousand = float(request.form['price_per_thousand'])

        try:
            cursor.execute(
                "UPDATE workers SET name = %s, price_per_thousand = %s WHERE id = %s",
                (name, price_per_thousand, worker_id)
            )
            conn.commit()
            flash("تم تحديث بيانات العامل بنجاح!", "success")
            return redirect(url_for('workers_management'))
        except Exception as e:
            conn.rollback()
            flash(f"حدث خطأ أثناء التحديث: {str(e)}", "error")

    # جلب بيانات العامل الحالية
    cursor.execute("SELECT * FROM workers WHERE id = %s", (worker_id,))
    worker = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template('edit_worker.html', worker=worker)


# 🗑️ حذف عامل
@app.route('/delete_worker/<int:worker_id>')
def delete_worker(worker_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM workers WHERE id = %s", (worker_id,))
        conn.commit()
        flash("تم حذف العامل بنجاح!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"حدث خطأ أثناء الحذف: {str(e)}", "error")

    cursor.close()
    conn.close()
    return redirect(url_for('workers_management'))


# 📝 إضافة عمل يومي للعامل (في الجدول الجديد)
@app.route('/add_daily_work', methods=['GET', 'POST'])
def add_daily_work():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # جلب جميع العمال النشطين
    cursor.execute("SELECT id, name, price_per_thousand FROM workers WHERE is_active = TRUE ORDER BY name")
    workers = cursor.fetchall()

    if request.method == 'POST':
        worker_id = int(request.form['worker_id'])
        quantity = int(request.form['quantity'])
        expenses = float(request.form.get('expenses', 0))
        work_date = request.form['work_date']

        try:
            # جلب سعر الألف للعامل
            cursor.execute("SELECT price_per_thousand FROM workers WHERE id = %s", (worker_id,))
            worker = cursor.fetchone()

            if worker:
                # تحويل Decimal إلى float للحساب
                price_per_thousand = float(worker['price_per_thousand'])

                # حساب المبلغ الإجمالي
                total_amount = (quantity / 1000) * price_per_thousand

                # إضافة العمل في الجدول الجديد (بعد التسوية)
                cursor.execute("""
                    INSERT INTO worker_work_after_settlement (worker_id, quantity, expenses, work_date, total_amount)
                    VALUES (%s, %s, %s, %s, %s)
                """, (worker_id, quantity, expenses, work_date, total_amount))

                conn.commit()
                flash(f"تم إضافة العمل اليومي بنجاح! المبلغ: {total_amount:.2f} جنيه", "success")
                return redirect(url_for('workers_daily_work'))
            else:
                flash("العامل غير موجود", "error")

        except Exception as e:
            conn.rollback()
            flash(f"حدث خطأ أثناء الإضافة: {str(e)}", "error")

    cursor.close()
    conn.close()

    # تمرير التاريخ الحالي
    from datetime import datetime
    current_date = datetime.now().strftime('%Y-%m-%d')
    return render_template('add_daily_work.html', workers=workers, current_date=current_date)


# 📊 عرض العمل اليومي (من الجدول الجديد)
@app.route('/workers_daily_work', methods=['GET', 'POST'])
def workers_daily_work():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # معالجة الفلترة
    selected_date = request.form.get('work_date', '')
    worker_id = request.form.get('worker_id', '')

    # بناء الاستعلام من الجدول الجديد
    query = """
        SELECT wdw.*, w.name as worker_name, w.price_per_thousand
        FROM worker_work_after_settlement wdw
        JOIN workers w ON wdw.worker_id = w.id
        WHERE 1=1
    """
    params = []

    if selected_date:
        query += " AND wdw.work_date = %s"
        params.append(selected_date)

    if worker_id:
        query += " AND wdw.worker_id = %s"
        params.append(worker_id)

    query += " ORDER BY wdw.work_date DESC, w.name"

    cursor.execute(query, tuple(params))
    daily_work = cursor.fetchall()

    # جلب العمال للقائمة المنسدلة
    cursor.execute("SELECT id, name FROM workers WHERE is_active = TRUE ORDER BY name")
    workers = cursor.fetchall()

    # حساب الإجماليات
    total_quantity = sum(item['quantity'] for item in daily_work)
    total_amount = sum(float(item['total_amount']) for item in daily_work)
    total_expenses = sum(float(item['expenses']) for item in daily_work)
    net_amount = total_amount - total_expenses

    cursor.close()
    conn.close()

    return render_template('workers_daily_work.html',
                           daily_work=daily_work,
                           workers=workers,
                           selected_date=selected_date,
                           worker_id=worker_id,
                           total_quantity=total_quantity,
                           total_amount=total_amount,
                           total_expenses=total_expenses,
                           net_amount=net_amount)


# 👤 صفحة خاصة بكل عامل (مع البيانات المنفصلة)
@app.route('/worker_profile/<int:worker_id>')
def worker_profile(worker_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # بيانات العامل
    cursor.execute("SELECT * FROM workers WHERE id = %s", (worker_id,))
    worker = cursor.fetchone()

    if not worker:
        flash("العامل غير موجود", "error")
        return redirect(url_for('workers_management'))

    # حساب الرصيد الحالي مباشرة
    cursor.execute("""
        SELECT 
            COALESCE(SUM(total_amount), 0) as total_income,
            COALESCE(SUM(expenses), 0) as total_expenses,
            COALESCE(SUM(total_amount - expenses), 0) as net_balance
        FROM worker_work_after_settlement 
        WHERE worker_id = %s
    """, (worker_id,))
    balance_result = cursor.fetchone()

    # تحويل النتيجة إلى قاموس بسيط
    current_balance = {
        'total_income': float(balance_result['total_income']) if balance_result['total_income'] else 0.0,
        'total_expenses': float(balance_result['total_expenses']) if balance_result['total_expenses'] else 0.0,
        'net_balance': float(balance_result['net_balance']) if balance_result['net_balance'] else 0.0
    }

    # العمل الشهري الحالي (من الجدول الجديد)
    cursor.execute("""
        SELECT 
            YEAR(work_date) as year,
            MONTH(work_date) as month,
            SUM(quantity) as total_quantity,
            SUM(total_amount) as total_income,
            SUM(expenses) as total_expenses,
            SUM(total_amount - expenses) as net_income
        FROM worker_work_after_settlement 
        WHERE worker_id = %s 
        GROUP BY YEAR(work_date), MONTH(work_date)
        ORDER BY year DESC, month DESC
    """, (worker_id,))
    current_monthly_work = cursor.fetchall()

    # العمل اليومي الحالي (آخر 30 يوم) - من الجدول الجديد
    cursor.execute("""
        SELECT * FROM worker_work_after_settlement 
        WHERE worker_id = %s 
        ORDER BY work_date DESC 
        LIMIT 30
    """, (worker_id,))
    current_daily_work = cursor.fetchall()

    # العمل الشهري التاريخي (من الجدول القديم)
    cursor.execute("""
        SELECT 
            YEAR(work_date) as year,
            MONTH(work_date) as month,
            SUM(quantity) as total_quantity,
            SUM(total_amount) as total_income,
            SUM(expenses) as total_expenses,
            SUM(total_amount - expenses) as net_income
        FROM worker_daily_work 
        WHERE worker_id = %s 
        GROUP BY YEAR(work_date), MONTH(work_date)
        ORDER BY year DESC, month DESC
    """, (worker_id,))
    historical_monthly_work = cursor.fetchall()

    # العمل اليومي التاريخي (من الجدول القديم)
    cursor.execute("""
        SELECT * FROM worker_daily_work 
        WHERE worker_id = %s 
        ORDER BY work_date DESC 
        LIMIT 30
    """, (worker_id,))
    historical_daily_work = cursor.fetchall()

    # التسويات
    cursor.execute("""
        SELECT * FROM worker_settlements 
        WHERE worker_id = %s 
        ORDER BY settlement_date DESC
    """, (worker_id,))
    settlements = cursor.fetchall()

    # إحصائيات سريعة حالية (من الجدول الجديد)
    cursor.execute("""
        SELECT 
            COUNT(*) as total_days,
            SUM(quantity) as total_quantity,
            SUM(total_amount) as total_income,
            SUM(expenses) as total_expenses,
            AVG(quantity) as avg_daily_quantity
        FROM worker_work_after_settlement 
        WHERE worker_id = %s
    """, (worker_id,))
    current_stats_result = cursor.fetchone()

    # تحويل الإحصائيات الحالية
    current_stats = {
        'total_days': current_stats_result['total_days'] if current_stats_result['total_days'] else 0,
        'total_quantity': current_stats_result['total_quantity'] if current_stats_result['total_quantity'] else 0,
        'total_income': float(current_stats_result['total_income']) if current_stats_result['total_income'] else 0.0,
        'total_expenses': float(current_stats_result['total_expenses']) if current_stats_result[
            'total_expenses'] else 0.0,
        'avg_daily_quantity': float(current_stats_result['avg_daily_quantity']) if current_stats_result[
            'avg_daily_quantity'] else 0.0
    }

    # إحصائيات تاريخية (من الجدول القديم)
    cursor.execute("""
        SELECT 
            COUNT(*) as total_historical_days,
            SUM(quantity) as total_historical_quantity,
            SUM(total_amount) as total_historical_income,
            SUM(expenses) as total_historical_expenses
        FROM worker_daily_work 
        WHERE worker_id = %s
    """, (worker_id,))
    historical_stats_result = cursor.fetchone()

    # تحويل الإحصائيات التاريخية
    historical_stats = {
        'total_historical_days': historical_stats_result['total_historical_days'] if historical_stats_result[
            'total_historical_days'] else 0,
        'total_historical_quantity': historical_stats_result['total_historical_quantity'] if historical_stats_result[
            'total_historical_quantity'] else 0,
        'total_historical_income': float(historical_stats_result['total_historical_income']) if historical_stats_result[
            'total_historical_income'] else 0.0,
        'total_historical_expenses': float(historical_stats_result['total_historical_expenses']) if
        historical_stats_result['total_historical_expenses'] else 0.0
    }

    cursor.close()
    conn.close()

    return render_template('worker_profile.html',
                           worker=worker,
                           current_balance=current_balance,
                           current_monthly_work=current_monthly_work,
                           current_daily_work=current_daily_work,
                           historical_monthly_work=historical_monthly_work,
                           historical_daily_work=historical_daily_work,
                           settlements=settlements,
                           current_stats=current_stats,
                           historical_stats=historical_stats)
# 🗑️ حذف عمل يومي
@app.route('/delete_daily_work/<int:work_id>')
def delete_daily_work(work_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM worker_daily_work WHERE id = %s", (work_id,))
        conn.commit()
        flash("تم حذف العمل اليومي بنجاح!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"حدث خطأ أثناء الحذف: {str(e)}", "error")

    cursor.close()
    conn.close()
    return redirect(request.referrer or url_for('workers_daily_work'))


# 📈 إحصائيات العمال
@app.route('/workers_stats')
def workers_stats():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # إحصائيات عامة
    cursor.execute("SELECT COUNT(*) as total_workers FROM workers")
    total_workers = cursor.fetchone()['total_workers']

    # إحصائيات العمل لهذا الشهر
    current_month = datetime.now().strftime('%Y-%m')
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT worker_id) as active_workers,
            SUM(quantity) as monthly_quantity,
            SUM(total_amount) as monthly_income,
            SUM(expenses) as monthly_expenses
        FROM worker_daily_work 
        WHERE DATE_FORMAT(work_date, '%Y-%m') = %s
    """, (current_month,))
    monthly_stats = cursor.fetchone()

    # تحويل Decimal إلى float
    if monthly_stats:
        monthly_stats['monthly_income'] = float(monthly_stats['monthly_income']) if monthly_stats[
            'monthly_income'] else 0.0
        monthly_stats['monthly_expenses'] = float(monthly_stats['monthly_expenses']) if monthly_stats[
            'monthly_expenses'] else 0.0

    # أفضل العمال لهذا الشهر
    cursor.execute("""
        SELECT 
            w.name,
            w.id,
            SUM(wdw.quantity) as total_quantity,
            SUM(wdw.total_amount) as total_income,
            SUM(wdw.total_amount - wdw.expenses) as net_income
        FROM worker_daily_work wdw
        JOIN workers w ON wdw.worker_id = w.id
        WHERE DATE_FORMAT(wdw.work_date, '%Y-%m') = %s
        GROUP BY w.id, w.name
        ORDER BY net_income DESC
        LIMIT 10
    """, (current_month,))
    top_workers = cursor.fetchall()

    # تحويل Decimal إلى float
    for worker in top_workers:
        worker['total_income'] = float(worker['total_income']) if worker['total_income'] else 0.0
        worker['net_income'] = float(worker['net_income']) if worker['net_income'] else 0.0

    cursor.close()
    conn.close()

    return render_template('workers_stats.html',
                           total_workers=total_workers,
                           monthly_stats=monthly_stats,
                           top_workers=top_workers,
                           current_month=current_month)


# 💰 تسوية حساب العامل مع نقل البيانات
@app.route('/worker_settlement/<int:worker_id>', methods=['GET', 'POST'])
def worker_settlement(worker_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # بيانات العامل
    cursor.execute("SELECT * FROM workers WHERE id = %s", (worker_id,))
    worker = cursor.fetchone()

    if not worker:
        flash("العامل غير موجود", "error")
        return redirect(url_for('workers_management'))

    # حساب الرصيد الحالي من الجدول الجديد
    cursor.execute("""
        SELECT 
            COALESCE(SUM(total_amount), 0) as total_income,
            COALESCE(SUM(expenses), 0) as total_expenses,
            COALESCE(SUM(total_amount - expenses), 0) as net_balance
        FROM worker_work_after_settlement 
        WHERE worker_id = %s
    """, (worker_id,))
    balance = cursor.fetchone()

    # تاريخ آخر تسوية
    cursor.execute("""
        SELECT MAX(settlement_date) as last_settlement_date 
        FROM worker_settlements 
        WHERE worker_id = %s
    """, (worker_id,))
    last_settlement_result = cursor.fetchone()

    if request.method == 'POST':
        settlement_amount = float(request.form['settlement_amount'])
        settlement_date = request.form['settlement_date']
        notes = request.form.get('notes', '')

        try:
            # 1. إضافة تسوية جديدة
            cursor.execute("""
                INSERT INTO worker_settlements (worker_id, settlement_amount, settlement_date, notes)
                VALUES (%s, %s, %s, %s)
            """, (worker_id, settlement_amount, settlement_date, notes))

            # 2. نقل البيانات من الجدول الجديد إلى الجدول القديم (للأرشيف)
            cursor.execute("""
                INSERT INTO worker_daily_work (worker_id, quantity, expenses, work_date, total_amount)
                SELECT worker_id, quantity, expenses, work_date, total_amount 
                FROM worker_work_after_settlement 
                WHERE worker_id = %s
            """, (worker_id,))

            # 3. حذف البيانات من الجدول الجديد (البداية من جديد)
            cursor.execute("""
                DELETE FROM worker_work_after_settlement 
                WHERE worker_id = %s
            """, (worker_id,))

            conn.commit()
            flash(f"تم تسوية الحساب بنجاح! المبلغ: {settlement_amount:.2f} جنيه - وبداية جديدة", "success")
            return redirect(url_for('worker_profile', worker_id=worker_id))

        except Exception as e:
            conn.rollback()
            flash(f"حدث خطأ أثناء التسوية: {str(e)}", "error")

    # سجل التسويات السابقة
    cursor.execute("""
        SELECT * FROM worker_settlements 
        WHERE worker_id = %s 
        ORDER BY settlement_date DESC
    """, (worker_id,))
    settlements = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('worker_settlement.html',
                           worker=worker,
                           balance=balance,
                           settlements=settlements,
                           last_settlement=last_settlement_result)




# 📊 حساب الرصيد الحالي (بعد آخر تسوية)
@app.route('/api/worker_balance/<int:worker_id>')
def api_worker_balance(worker_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # تاريخ آخر تسوية
        cursor.execute("""
            SELECT MAX(settlement_date) as last_settlement_date 
            FROM worker_settlements 
            WHERE worker_id = %s
        """, (worker_id,))
        last_settlement = cursor.fetchone()

        # حساب الرصيد من بعد آخر تسوية
        if last_settlement and last_settlement['last_settlement_date']:
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(total_amount), 0) as total_income,
                    COALESCE(SUM(expenses), 0) as total_expenses,
                    COALESCE(SUM(total_amount - expenses), 0) as net_balance
                FROM worker_daily_work 
                WHERE worker_id = %s AND work_date > %s
            """, (worker_id, last_settlement['last_settlement_date']))
        else:
            # إذا لا توجد تسويات سابقة، احسب كل التاريخ
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(total_amount), 0) as total_income,
                    COALESCE(SUM(expenses), 0) as total_expenses,
                    COALESCE(SUM(total_amount - expenses), 0) as net_balance
                FROM worker_daily_work 
                WHERE worker_id = %s
            """, (worker_id,))

        balance = cursor.fetchone()

        return jsonify({
            'success': True,
            'net_balance': float(balance['net_balance']),
            'total_income': float(balance['total_income']),
            'total_expenses': float(balance['total_expenses']),
            'last_settlement_date': last_settlement['last_settlement_date'] if last_settlement else None
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })
    finally:
        cursor.close()
        conn.close()


# 🔧 روت للتحقق من البيانات
@app.route('/debug_worker/<int:worker_id>')
def debug_worker(worker_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # التحقق من البيانات في الجداول
    cursor.execute("SELECT COUNT(*) as count FROM worker_work_after_settlement WHERE worker_id = %s", (worker_id,))
    work_count = cursor.fetchone()

    cursor.execute("SELECT * FROM worker_work_after_settlement WHERE worker_id = %s", (worker_id,))
    work_data = cursor.fetchall()

    cursor.execute(
        "SELECT SUM(total_amount) as total, SUM(expenses) as expenses FROM worker_work_after_settlement WHERE worker_id = %s",
        (worker_id,))
    totals = cursor.fetchone()

    cursor.close()
    conn.close()

    return jsonify({
        'work_count': work_count,
        'work_data': work_data,
        'totals': totals
    })


@app.function()
@modal.wsgi_app()
def run_flask():
    return flask_app

