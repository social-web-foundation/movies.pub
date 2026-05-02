# movies.pub

ActivityPub object server that maps movies from Wikidata into Activity Streams Video objects

[ActivityPub objects](https://www.w3.org/TR/activitypub#objects) can be used in activities, but they must have an [Activity Streams 2.0](https://www.w3.org/TR/activitystreams-core/) document available at the `id` URL.

This server provides an URL for each film in the [Wikidata](https://www.wikidata.org/) database, and a `search` endpoint to make it easy to find films.

## Table of Contents

- [Security](#security)
- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [API](#api)
- [Contributing](#contributing)
- [License](#license)

## Security

Please use the [security disclosure](https://github.com/social-web-foundation/movies.pub/security) system to report any security issues with this applications.

## Install

This server is available at [movies.pub](https://movies.pub/) and you don't have to install it to use it. However, if you want to install it, you can use the [Helm](https://helm.sh/) chart in `charts/movies-pub` like so:

```bash
helm upgrade --install movies-pub charts/movies-pub -f <your-values-file.yaml>
```

You'll need to have a Kubernetes cluster, and use a values file to set your particular settings.

## Usage

The main way to use this service is in ActivityPub applications. A good example would be a `View` activity for a movie:

```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "id": "https://social.example/user/evanp/view/3",
  "type": "View",
  "actor": "https://social.example/user/evanp",
  "object": "https://movies.pub/movie/Q107105860",
  "summary": "Evan watched 'Project Hail Mary'"
}
```

## API

### https://movies.pub/movie/{q-item}

This returns an ActivityPub object representing the movie. Its type is [Video](https://www.w3.org/TR/activitystreams-vocabulary/#dfn-video). It will have at least a [name](https://www.w3.org/TR/activitystreams-vocabulary/#dfn-name) property and possibly other properties.

```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "id": "https://movies.pub/movie/Q117037697",
  "type": "Video",
  "name": "Anatomy of a Fall"
}
```

### https://movies.pub/search/movie{?q,lng}

This is a search endpoint for finding movies with a given word in the title -- the `q` parameter is the search value. The `lng` is a hint for the language of the film name.

It returns an Activity Streams [Collection](https://www.w3.org/TR/activitystreams-core/#dfn-collection) object with the `totalItems` as the count, and the

```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "id": "https://movies.pub/search/movie?q=foo&lng=en",
  "summary": "movies.pub search results for 'foo' in 'en'",
  "totalItems": 2,
  "items": [
    {
      "id": "https://movies.pub/movie/Q1759260",
      "name": "To Wong Foo, Thanks for Everything! Julie Newmar"
    },
    {
      "id": "https://movies.pub/movie/Q2878380",
      "name": "Foo Fighters: Back and Forth"
    }
  ]
}
```

## Contributing

PRs are accepted. Please [add an issue](https://github.com/social-web-foundation/movies.pub/issues) first, and refer to it from your PR.

The stack for this project:

- [Python](https://python.org/) - programming language
- [uv](https://docs.astral.sh/uv/) - package manager
- [FastAPI](https://fastapi.tiangolo.com) - web API server
- [pytest](https://docs.pytest.org/) - testing framework

Tests are in `./tests/`. It's a good idea to add a test for any functionality you need to add. You can run the tests with `uv run pytest`.

To run the server locally, use this command:

```bash
uv run uvicorn main:app --reload
```

This will run a local server on port 8000. You can load it in your browser at `http://127.0.0.1:8000/`.

## License

movies.pub - movies data server for ActivityPub

Copyright (C) 2026 Social Web Foundation, Lorenzo Caresio

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along
with this program.  If not, see <https://www.gnu.org/licenses/>.
