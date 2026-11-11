#include "lob/order_book.hpp"

#include <algorithm>
#include <limits>
#include <stdexcept>

namespace lob {
namespace {
void order_side(const std::string& side) {
    if (side != "BUY" && side != "SELL") throw std::invalid_argument("invalid order side");
}
void clean(Levels& levels) {
    for (auto it = levels.begin(); it != levels.end();) {
        if (it->first <= 0 || it->second < 0) throw std::invalid_argument("invalid level");
        if (it->second == 0) it = levels.erase(it); else ++it;
    }
}
}
void validate(const Event& e) {
    if (e.type != "ADD" && e.type != "CANCEL" && e.type != "TRADE")
        throw std::invalid_argument("invalid event type");
    if (e.side != "BID" && e.side != "ASK") throw std::invalid_argument("invalid book side");
    if (e.price <= 0 || e.quantity < 0) throw std::invalid_argument("invalid event value");
}
OrderBook::OrderBook(Levels bids, Levels asks) : bids_(std::move(bids)), asks_(std::move(asks)) {
    clean(bids_); clean(asks_);
}
std::optional<Integer> OrderBook::best_bid() const {
    if (bids_.empty()) return std::nullopt;
    return bids_.rbegin()->first;
}
std::optional<Integer> OrderBook::best_ask() const {
    if (asks_.empty()) return std::nullopt;
    return asks_.begin()->first;
}
void OrderBook::apply(const Event& e) {
    validate(e);
    auto& levels = e.side == "BID" ? bids_ : asks_;
    auto it = levels.find(e.price);
    const auto current = it == levels.end() ? 0 : it->second;
    Integer quantity;
    if (e.type == "ADD") {
        if (e.quantity > std::numeric_limits<Integer>::max() - current)
            throw std::invalid_argument("quantity overflow");
        quantity = current + e.quantity;
    } else {
        if (it == levels.end() || e.quantity > current)
            throw std::invalid_argument("removal exceeds liquidity");
        quantity = current - e.quantity;
    }
    if (quantity) levels[e.price] = quantity;
    else if (it != levels.end()) levels.erase(it);
}
void OrderBook::apply_all(const std::vector<Event>& events) {
    for (const auto& event : events) apply(event);
}
Execution OrderBook::execute(const std::string& side, Integer quantity) {
    order_side(side);
    if (quantity < 0) throw std::invalid_argument("negative order quantity");
    Execution result{quantity, 0, quantity, std::nullopt, {}};
    auto& levels = side == "BUY" ? asks_ : bids_;
    long double notional = 0;
    while (result.remaining && !levels.empty()) {
        auto it = side == "BUY" ? levels.begin() : std::prev(levels.end());
        const auto filled = std::min(result.remaining, it->second);
        result.fills.push_back({it->first, filled});
        notional += static_cast<long double>(it->first) * filled;
        result.remaining -= filled;
        it->second -= filled;
        if (it->second == 0) levels.erase(it);
    }
    result.filled = quantity - result.remaining;
    if (result.filled) result.average_price = static_cast<double>(notional / result.filled / 100);
    return result;
}
PassiveOrder::PassiveOrder(std::string order_side_value, Integer p, Integer q, Integer a, bool c)
    : price(p), original(q), remaining(q), ahead(a), side(std::move(order_side_value)),
      cancellations_ahead_(c) {
    order_side(side);
    if (p <= 0 || q <= 0 || a < 0) throw std::invalid_argument("invalid passive order");
}
void PassiveOrder::cancel() { if (status != "FILLED") status = "CANCELLED"; }
void PassiveOrder::update(const Event& e, Integer index) {
    validate(e);
    if (status == "FILLED" || status == "CANCELLED") return;
    if (e.side != (side == "BUY" ? "BID" : "ASK") || e.price != price || e.type == "ADD") return;
    if (e.type == "CANCEL" && !cancellations_ahead_) return;
    const auto removed = std::min(ahead, e.quantity);
    ahead -= removed;
    if (e.type == "CANCEL") { cancelled_ahead += removed; return; }
    traded_ahead += removed;
    const auto filled = std::min(remaining, e.quantity - removed);
    if (filled) {
        remaining -= filled;
        fills.push_back({index, {price, filled}});
        status = remaining ? "PARTIAL" : "FILLED";
    }
}
} // namespace lob
