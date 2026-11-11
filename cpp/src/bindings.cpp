#include "lob/order_book.hpp"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <chrono>

namespace py = pybind11;
using namespace lob;
PYBIND11_MODULE(_lob_cpp, module) {
    py::class_<Event>(module, "Event")
        .def(py::init<std::string, std::string, Integer, Integer>());
    py::class_<Fill>(module, "Fill")
        .def_readonly("price", &Fill::price).def_readonly("quantity", &Fill::quantity);
    py::class_<Execution>(module, "Execution")
        .def_readonly("requested_quantity", &Execution::requested)
        .def_readonly("filled_quantity", &Execution::filled)
        .def_readonly("remaining_quantity", &Execution::remaining)
        .def_readonly("average_price", &Execution::average_price)
        .def_readonly("fills", &Execution::fills);
    py::class_<OrderBook>(module, "OrderBook")
        .def(py::init<Levels, Levels>(), py::arg("bids") = Levels{}, py::arg("asks") = Levels{})
        .def_property_readonly("bids", &OrderBook::bids)
        .def_property_readonly("asks", &OrderBook::asks)
        .def_property_readonly("best_bid", &OrderBook::best_bid)
        .def_property_readonly("best_ask", &OrderBook::best_ask)
        .def("apply", &OrderBook::apply)
        .def("apply_all", &OrderBook::apply_all)
        .def("execute", &OrderBook::execute);
    py::class_<PassiveOrder>(module, "PassiveOrder")
        .def(py::init<std::string, Integer, Integer, Integer, bool>(),
             py::arg("side"), py::arg("price"), py::arg("quantity"), py::arg("ahead"),
             py::arg("cancellations_ahead") = true)
        .def("update", &PassiveOrder::update).def("cancel", &PassiveOrder::cancel)
        .def_readonly("remaining_quantity", &PassiveOrder::remaining)
        .def_readonly("quantity_ahead", &PassiveOrder::ahead)
        .def_readonly("traded_ahead", &PassiveOrder::traded_ahead)
        .def_readonly("cancelled_ahead", &PassiveOrder::cancelled_ahead)
        .def_readonly("fills", &PassiveOrder::fills)
        .def_readonly("status", &PassiveOrder::status);
    module.def("time_replay", [](const OrderBook& initial, const std::vector<Event>& events) {
        auto book = initial;
        const auto start = std::chrono::steady_clock::now();
        book.apply_all(events);
        const auto seconds = std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        return py::make_tuple(seconds, book);
    });
}
