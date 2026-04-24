from foxpilot.readability import extract_main_content


class _Element:
    def __init__(self, text):
        self.text = text


class _Driver:
    def __init__(self, body_text="", js_text=""):
        self.body_text = body_text
        self.js_text = js_text

    def find_element(self, by, selector):
        if selector == "body":
            return _Element(self.body_text)
        raise Exception("not found")

    def execute_script(self, script):
        return self.js_text


def test_extract_main_content_uses_dom_text_when_body_text_is_blank():
    driver = _Driver(body_text="", js_text="Example Domain\nLearn more")

    text = extract_main_content(driver)

    assert text == "Example Domain\nLearn more"
