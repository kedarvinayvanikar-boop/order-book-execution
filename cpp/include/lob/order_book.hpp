#pragma once

#include <cstdint>
#include <map>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace lob {
using Integer = std::int64_t;
using Levels = std::map<Integer, Integer>;

struct Event {
    std::string type;
    std::string side;
    Integer price;
    Integer quantity;
};
struct Fill { Integer price; Integer quantity; };
struct Execution {
    Integer requested;
    Integer filled;
    Integer remaining;
    std::optional<double> average_price;
    std::vector<Fill> fills;
};

class OrderBook {
public:
    OrderBook(Levels bids = {}, Levels asks = {});
    const Levels& bids() const { return bids_; }
    const Levels& asks() const { return asks_; }
    std::optional<Integer> best_bid() const;
    std::optional<Integer> best_ask() const;
    void apply(const Event& event);
    void apply_all(const std::vector<Event>& events);
    Execution execute(const std::string& side, Integer quantity);
private:
    Levels bids_, asks_;
};

class PassiveOrder {
public:
    PassiveOrder(std::string side, Integer price, Integer quantity, Integer ahead,
                 bool cancellations_ahead = true);
    void update(const Event& event, Integer event_index);
    void cancel();
    Integer price, original, remaining, ahead, traded_ahead = 0, cancelled_ahead = 0;
    std::string side, status = "OPEN";
    std::vector<std::pair<Integer, Fill>> fills;
private:
    bool cancellations_ahead_;
};
void validate(const Event& event);
} // namespace lob
