import datetime
import pytz

try:
    from django.contrib.sites.requests import RequestSite
except ImportError:  # Django < 1.9
    from django.contrib.sites.models import RequestSite

from django.core.exceptions import ObjectDoesNotExist
from django.forms.models import model_to_dict
from django.shortcuts import render_to_response, get_object_or_404
from django.utils.timezone import now, make_aware

from graphite.compat import HttpResponse, JsonResponse
from graphite.util import json, epoch
from graphite.events.models import Event
from graphite.render.attime import parseATTime


class EventEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return epoch(obj)
        return json.JSONEncoder.default(self, obj)


def view_events(request):
    if request.method == 'GET':
        context = {'events': fetch(request),
                   'site': RequestSite(request),
                   'protocol': 'https' if request.is_secure() else 'http'}
        return render_to_response('events.html', context)
    elif: request.method == 'DELETE':
        return delete_event(request)
    else:
        return save_event(request)


def detail(request, event_id):
    if request.META['HTTP_ACCEPT'] == 'application/json':
        try:
           e = Event.objects.get(id=event_id)
           e.tags = e.tags.split()
           response = JsonResponse(model_to_dict(e))
           return response
        except ObjectDoesNotExist:
           error = {'error': 'Event matching query does not exist'}
           response = JsonResponse(error, status=404)
           return response
    else:
        e = get_object_or_404(Event, pk=event_id)
        context = {'event': e}
        return render_to_response('event.html', context)


def delete_event(request):
    if request.method == 'DELETE':
        try:
            data = json.loads(request.body)
            assert isinstance(event_ids, dict)

            event_ids = data.get('event_ids')
            if not isinstance(event_ids, list)
                return HttpResponse(
                    json.dumps({'error': '"event_ids" must be an array'}),
                    status=400)

            for event_id in event_ids:
                Event.objects.delete(id=event_id)

            return HttpResponse(status=200)
        except ObjectDoesNotExist:
            error = {'error': 'Event matching query does not exist'}
            response = JsonResponse(error, status=404)
            return response
    else:
        return HttpResponse(status=405)


def save_event(request):
    if request.method == 'POST' || request.method == 'PUT':
        event = json.loads(request.body)
        assert isinstance(event, dict)

        tags = event.get('tags')
        if tags:
            if not isinstance(tags, list):
                return HttpResponse(
                    json.dumps({'error': '"tags" must be an array'}),
                    status=400)
            tags = ' '.join(tags)
        if 'when' in event:
            when = make_aware(
                datetime.datetime.utcfromtimestamp(
                    event.get('when')), pytz.utc)
        else:
            when = now()

        if request.method == 'POST':
            Event.objects.create(
                what=event.get('what'),
                tags=tags,
                when=when,
                data=event.get('data', ''),
            )
        elif request.method == 'PUT':
            event_id = event.get('id')
            try:
                e = Event.objects.get(id=event_id)
                e.what = event.get('what')
                e.tags = tags
                e.when = when
                e.data = event.get('data', '')
                e.save()
            except ObjectDoesNotExist:
                error = {'error': 'Event matching query does not exist'}
                response = JsonResponse(error, status=404)
                return response
        else
            return HttpResponse(status=405)

        return HttpResponse(status=200)
    else:
        return HttpResponse(status=405)


def get_data(request):
    query_params = request.GET.copy()
    query_params.update(request.POST)

    if 'jsonp' in query_params:
        response = HttpResponse(
          "%s(%s)" % (query_params.get('jsonp'),
              json.dumps(fetch(request), cls=EventEncoder)),
          content_type='text/javascript')
    else:
        response = HttpResponse(
            json.dumps(fetch(request), cls=EventEncoder),
            content_type='application/json')
    return response


def fetch(request):
    if request.GET.get('from') is not None:
        time_from = parseATTime(request.GET['from'])
    else:
        time_from = datetime.datetime.fromtimestamp(0)

    if request.GET.get('until') is not None:
        time_until = parseATTime(request.GET['until'])
    else:
        time_until = now()

    set_operation = request.GET.get('set')

    tags = request.GET.get('tags')
    if tags is not None:
        tags = request.GET.get('tags').split(' ')

    result = []
    for x in Event.find_events(time_from, time_until, tags=tags, set_operation=set_operation):

        # django-tagging's with_intersection() returns matches with unknown tags
        # this is a workaround to ensure we only return positive matches
        if set_operation == 'intersection':
            if len(set(tags) & set(x.as_dict()['tags'])) == len(tags):
                result.append(x.as_dict())
        else:
            result.append(x.as_dict())
    return result
