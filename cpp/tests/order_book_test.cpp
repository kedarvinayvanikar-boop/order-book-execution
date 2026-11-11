#include "lob/order_book.hpp"
#include <cmath>
#include <stdexcept>

void require(bool condition) { if (!condition) throw std::runtime_error("test assertion failed"); }
int main() {
    using namespace lob;
    OrderBook book({{5000, 100}}, {{5004, 250}, {5005, 300}, {5006, 500}});
    auto execution = book.execute("BUY", 600);
    require(execution.filled == 600 && execution.remaining == 0 && execution.fills.size() == 3);
    require(std::abs(*execution.average_price - 50.0466666666667) < 1e-10);
    require(book.best_ask() == 5006 && book.asks().at(5006) == 450);
    book.apply({"TRADE", "BID", 5000, 100});
    require(!book.best_bid());
    auto before = book.asks();
    try { book.apply({"CANCEL", "ASK", 5006, 451}); require(false); }
    catch (const std::invalid_argument&) {}
    require(book.asks() == before);
    require(!OrderBook{}.execute("BUY", 100).average_price);
    PassiveOrder order("BUY", 5000, 50, 100);
    order.update({"CANCEL", "BID", 5000, 40}, 0);
    order.update({"TRADE", "BID", 5000, 80}, 1);
    require(order.ahead == 0 && order.remaining == 30 && order.status == "PARTIAL");
    order.update({"TRADE", "BID", 5000, 100}, 2);
    require(order.remaining == 0 && order.status == "FILLED");
}
