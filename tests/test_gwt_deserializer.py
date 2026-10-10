"""
Offline tests for the schedule GWT deserializer, using a synthetic response
(real responses contain other students' names, so they are not committed).
"""
import json
from datetime import datetime

import pytest

from studieplus_api.gwt_deserializer import GWTDeserializer, parse_schedule_response

SKEMA = "dk.uddata.model.skema"
START = datetime(2026, 9, 28, 8, 15)
END = datetime(2026, 9, 28, 9, 15)


class Payload:
    """Synthetic GWT-RPC response. Values are added in the order the deserializer reads them."""

    def __init__(self):
        self.values = []
        self.strings = []

    def int(self, value):
        self.values.append(value)
        return self

    def bool(self, value):
        return self.int(1 if value else 0)

    def string(self, text):
        if text is None:
            return self.int(0)
        if text not in self.strings:
            self.strings.append(text)
        return self.int(self.strings.index(text) + 1)

    def null(self, count=1):
        for _ in range(count):
            self.int(0)
        return self

    def obj(self, class_name):
        return self.string(f"{class_name}/1")

    def array(self, count):
        return self.obj("java.util.ArrayList").int(count)

    def udate(self, dt):
        self.obj("dk.uddata.gwt.comm.shared.UDate").string("UDate:")
        return self.int(dt.year - 1900).int(dt.month - 1).int(dt.day).int(dt.hour).int(dt.minute).int(dt.second)

    def response(self):
        return "//OK" + json.dumps(list(reversed(self.values)) + [self.strings, 0, 7])


def write_lesson(p, extra_object=None):
    """SkemaBegivenhed, field by field in the order of the JS deserializer."""
    p.obj(f"{SKEMA}.SkemaBegivenhed")
    p.array(1).obj(f"{SKEMA}.SkemaBegivenhed$AktiviteterISkema").int(1).int(2).string("HOLD").string("htxqr24").int(3)  # a
    p.string(None).string(None).bool(False).int(0)                                    # c, d, e, f
    if extra_object:
        extra_object(p)                                                                # g
    else:
        p.null()
    p.array(2)                                                                         # i
    for name in ("Elev Et", "Elev To"):
        p.obj(f"{SKEMA}.SkemaBegivenhed$ElevISkema").string("E1").string(name).int(7).string("htxqr24")
    p.int(0).null().bool(False)                                                        # j, k, n
    p.array(1).obj(f"{SKEMA}.SkemaBegivenhed$FagISkema").int(5).string("Matematik")    # o
    p.null().int(0).null().int(0)                                                      # p, q, r, s
    p.string("Matematik").bool(False).int(0)                                           # t, u, w
    p.array(1).obj(f"{SKEMA}.SkemaBegivenhed$LokalerISkema").int(11).string("M1304").int(0)  # A
    p.bool(False)                                                                      # B
    p.array(1).obj(f"{SKEMA}.SkemaBegivenhed$MedarbejderISkema").int(21).string("abcd").int(0).null()  # C
    p.bool(False).string(None).null().string(None).bool(False).string(None).bool(False)  # D, F, G, H, I, J, K
    p.null().null()                                                                    # L, M
    p.obj("java.lang.Integer").int(8529907)                                            # N (lesson id)
    p.null().string(None)                                                              # O, P
    p.udate(END).udate(START)                                                          # Q, R
    p.obj(f"{SKEMA}.SkemaBegivenhed$Status").int(0)                                    # S
    p.int(0).bool(False)                                                               # T, V


def schedule_response(extra_object=None, unread_values=0):
    """PersSkemaData with one day containing one lesson."""
    p = Payload()
    p.obj(f"{SKEMA}.PersSkemaData")
    p.null(8).int(0).int(0).int(0).int(0).int(0)           # 1-13
    p.null().bool(False).int(0).int(0).null(3)             # 14-20
    p.obj("java.util.HashMap").int(1).udate(START)         # 21: {date -> [lessons]}
    p.array(1)
    write_lesson(p, extra_object)
    p.null()                                               # 22: notes
    p.null(unread_values)
    return p.response()


def test_lesson_with_nested_types_parses_strictly():
    lessons = parse_schedule_response(schedule_response(), strict=True)

    assert len(lessons) == 1
    lesson = lessons[0]
    assert lesson.lesson_id == 8529907
    assert lesson.subject == "Matematik"
    assert lesson.class_name == "htxqr24"
    assert lesson.rooms == ["M1304"]
    assert lesson.teachers == ["abcd"]
    assert (lesson.start_time, lesson.end_time) == (START, END)


def test_strict_raises_when_stack_is_not_fully_consumed():
    response = schedule_response(unread_values=1)

    assert len(parse_schedule_response(response)) == 1
    with pytest.raises(ValueError, match="left unread"):
        parse_schedule_response(response, strict=True)


def test_strict_raises_on_class_without_deserializer():
    response = schedule_response(extra_object=lambda p: p.obj(f"{SKEMA}.SomethingNew"))

    with pytest.raises(ValueError, match="SomethingNew"):
        parse_schedule_response(response, strict=True)


def test_nested_class_is_not_routed_to_its_outer_class():
    """SkemaBegivenhed$X must not fall back to the SkemaBegivenhed deserializer."""
    parser = GWTDeserializer(Payload().obj(f"{SKEMA}.SkemaBegivenhed$Unregistered").response())

    obj = parser._read_object()

    assert obj.get("_unknown"), f"routed to another deserializer: {obj!r}"
    assert parser.pos == 0


def test_assignments_strict_mode():
    empty = Payload().array(0)
    assert GWTDeserializer(empty.response()).parse_assignments(strict=True) == []

    with_unread_value = Payload().array(0).null()
    assert GWTDeserializer(with_unread_value.response()).parse_assignments() == []
    with pytest.raises(ValueError, match="left unread"):
        GWTDeserializer(with_unread_value.response()).parse_assignments(strict=True)


def write_frava(p):
    """Frava, field by field in the order of the JS deserializer."""
    p.obj(f"{SKEMA}.Frava")
    p.obj("java.lang.Integer").int(42).int(3).null()      # object, int, object
    p.udate(START).string("Fravær").string(None)          # UDate, string, string
    p.udate(START).udate(END)                             # UDate, UDate
    p.obj(f"{SKEMA}.Frava$Status").int(1)                 # Frava$Status
    p.string("Bemærkning")                                # string


def test_lesson_with_frava_parses_strictly():
    lessons = parse_schedule_response(schedule_response(extra_object=write_frava), strict=True)

    assert len(lessons) == 1
    assert lessons[0].lesson_id == 8529907
    assert (lessons[0].start_time, lessons[0].end_time) == (START, END)
