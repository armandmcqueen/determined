import sys


def inner():
    print("inner")
    frame = sys._getframe(1)
    print(f"Function calling inner(): {frame.f_code.co_name}, {frame.f_code.co_filename}")

def outer():
    print("outer")
    inner()


if __name__ == '__main__':
    outer()