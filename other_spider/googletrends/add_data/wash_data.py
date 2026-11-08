content = """


"""

# content = repr(content)

for row in content.strip().split('\n'):
    if 'replace into ' in row:
        print(row)
