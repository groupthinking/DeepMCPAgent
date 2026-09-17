# CLI

Use DeepMCPAgent without writing Python.

## List tools

```bash
deepmcpagent list-tools \
  --http 'name=math url=http://127.0.0.1:8000/mcp transport=http' \
  --model-id "openai:gpt-4.1"
```

## Interactive chat

```bash
deepmcpagent run \
  --http 'name=math url=http://127.0.0.1:8000/mcp transport=http' \
  --model-id "openai:gpt-4.1"
```

## Server block grammar

Each `--http` or `--stdio` occurrence consumes **one shell-quoted structured value**. Repeat
the option to add servers; attached forms such as `--http='name=... url=...'` are also
accepted. Servers retain their actual command-line order even when HTTP and stdio occurrences
are mixed.

- `--http 'name=NAME url=HTTP_URL [transport=http|streamable-http|sse] [header.X=Y] [auth=VALUE]'`
- `--stdio 'name=NAME command=COMMAND [args="..."] [env.X=Y] [cwd=PATH] [keep_alive=true|false]'`
- `--model-id` is required and is passed to LangChain's `init_chat_model`.
- `--instructions` overrides the system prompt.

`name`, `url`, and `command` must be nonempty where required. HTTP URLs must be absolute
`http://` or `https://` URLs. Only the keys shown above are accepted; `header.X` and `env.X`
require a nonempty suffix. Values may contain `=`. Quote a value inside the block when that
value itself contains spaces, as shown for `args` and the authorization header below.

> **Migration:** The former unquoted multi-token form
> `--http name=math url=http://127.0.0.1:8000/mcp` is no longer accepted. Quote the complete
> block so the shell passes it as the option's single value.

## Examples

```bash
# With auth header
deepmcpagent list-tools \
  --http 'name=ext url=https://api.example.com/mcp transport=http header.Authorization="Bearer TOKEN"' \
  --model-id "anthropic:claude-3-5-sonnet-latest"

# Mixed repeatable blocks, including attached syntax
deepmcpagent list-tools \
  --http 'name=remote url=https://api.example.com/mcp?token=a=b transport=streamable-http' \
  --stdio='name=local command=python args="-m example.server --token=a=b" env.MODE=dev keep_alive=false' \
  --model-id "openai:gpt-4.1"
```
