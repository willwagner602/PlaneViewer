from random import shuffle

from django.shortcuts import render, HttpResponseRedirect
from django.contrib.staticfiles.templatetags.staticfiles import static


from .models import Aircraft, AircraftType, UserHistory
from .forms import AircraftForm, ErrorForm


def aircraft_static_location(aircraft):
    return static('AircraftSpotter/images/' + aircraft.location + '/' + aircraft.name)


def aircraft_test(request):

    # get the individual plane for display, and the necessary data to display it
    plane = Aircraft.objects.filter(use_flag=True).order_by('?').first()

    # get information necessary to identify similar planes for challenging multiple choice options
    plane_model = plane.aircraft
    type_int = AircraftType.objects.get(aircraft_name=plane_model).type_int

    # get selection for multiple choice options
    selection_options = AircraftType.objects.filter(type_int__exact=type_int).order_by('?').all()

    # exclude the correct answer
    selection_options = selection_options.exclude(aircraft_name__exact=plane_model)

    # get 5 aircraft names and create a list of them, then add the correct answer
    selection_options = [str(plane) for plane in selection_options[:5]]
    selection_options.append(plane_model)

    # if there weren't 5 other aircraft of type, complete the list to 6 with random aircraft
    selection_difference = 6 - len(selection_options)
    if selection_difference > 0:
        additional_selection_options = AircraftType.objects.order_by('?').all()
        additional_selection_options = additional_selection_options.exclude(aircraft_name__in=selection_options)
        selection_options += additional_selection_options[:selection_difference]

    # randomize the selection and create the left and right lists for the final page
    shuffle(selection_options)

    page_vars = {'selections': selection_options,
                 'location': aircraft_static_location(plane),
                 'author': plane.author,
                 'aircraft_id': plane.image_id,
                 'error_url': 'error_report/' + str(plane.image_id)
                 }

    if request.method == 'POST':
        # get the plane's id and the guess
        guessed_aircraft = Aircraft.objects.get(image_id=request.POST['aircraft_id'])
        current_type = guessed_aircraft.aircraft
        user_guess = request.POST['answer']

        # return a message about whether the guess was accurate
        if current_type == user_guess:
            success = "Correct"
            corrected_guess = ""
        else:
            success = 'Wrong'
            corrected_guess = 'You guessed {}, it was {}'.format(user_guess, current_type)

        page_vars['success'] = success
        page_vars['last_aircraft_location'] = aircraft_static_location(guessed_aircraft)
        page_vars['corrected_aircraft'] = corrected_guess
        page_vars['success_image_overlay'] = static("AircraftSpotter/{}.png".format(success))

        # for authenticated users, add this aircraft to their history
        if request.user.is_authenticated():
            try:
                user_history = UserHistory.objects.get(user_id=request.user.pk)
            except UserHistory.DoesNotExist:
                user_history = UserHistory.create(request.user.pk)
                user_history.save()

            user_history.add_history(plane.pk, success + "!" + corrected_guess)

    return render(request, 'AircraftSpotter/aircraft_spotter.html', page_vars)


def error_report(request, current_image_id):

    plane = Aircraft.objects.get(image_id=current_image_id)
    image_location = static('AircraftSpotter/images/' + plane.location + '/' + plane.name)

    page_vars = {
        'image_id': current_image_id,
        'image_location': image_location,
        'plane': plane.aircraft,
        'error_url': str(plane.image_id),
    }

    # serve admins the data management page
    if request.user.is_superuser:
        return HttpResponseRedirect('/data/' + current_image_id)

    if request.method == 'POST':
        data = request.POST

        error_form = ErrorForm(data)

        if error_form.is_valid():

            # store the error report, return to page with success and the error data
            error_form.save()

            page_vars['success'] = 'Thanks for your error report!'

            if 'wrong_aircraft' in data:
                wrong_aircraft = data['wrong_aircraft']
                page_vars['wrong_aircraft'] = wrong_aircraft

            if 'bad_picture' in data:
                bad_picture = data['bad_picture']
                page_vars['bad_picture'] = bad_picture

            if 'copyright' in data:
                copyright_data = data['copyright']
                page_vars['copyright'] = copyright_data

            if 'open_response' in data:
                open_response = data['open_response']
                page_vars['open_response'] = open_response

        else:
            page_vars['errors'] = error_form.errors

        return render(request, 'AircraftSpotter/error_report.html', page_vars)

    # serve regular users the error page
    else:
        return render(request, 'AircraftSpotter/error_report.html', page_vars)


def aircraft_data(request, current_image_id):

    aircraft = Aircraft.objects.get(image_id=current_image_id)
    data_url = current_image_id

    use_flag = False
    redownload_flag = False

    page_vars = {
        'data_url': data_url
    }

    if request.method == 'POST':

        aircraft_form = AircraftForm(request.POST, instance=aircraft)

        if aircraft_form.is_valid():
            aircraft_form.save()

            # return the updated form instance of the same plane they were just looking at
            page_vars['success'] = 'Plane saved!'

        else:
            page_vars['errors'] = aircraft_form.errors

    current_aircraft_data = aircraft.data()
    page_vars['aircraft_data'] = current_aircraft_data
    page_vars['location'] = aircraft_static_location(aircraft)

    if current_aircraft_data['use_flag'] == 1:
        use_flag = True

    if current_aircraft_data['redownload_flag'] == 1:
        redownload_flag = True

    return render(request, 'AircraftSpotter/aircraft_data.html', page_vars)


def convert_image_list_to_rows(user_history, row_length=6):
    history_in_rows = []
    current_row = []
    image_count = 0

    print("Length of user history is ", len(user_history))
    print(user_history)

    for image in user_history:

        if image_count < row_length:
            current_row.append(image)
            image_count += 1
        else:
            history_in_rows.append(current_row)
            current_row = [image,]
            image_count = 1

    history_in_rows.append(current_row)
    return history_in_rows


def data_manager(request):

    page_vars = {}

    if request.user.is_authenticated():

        aircraft_types = AircraftType.objects.all().order_by('aircraft_name')
        page_vars['aircraft_types'] = [aircraft.aircraft_name for aircraft in aircraft_types]

        if request.method == 'POST':
            # if the user is requesting data, get all the entries for that plane and return them
            requested_aircraft = request.POST['aircraft']
            aircraft = Aircraft.objects.filter(aircraft=requested_aircraft, redownload_flag__exact=0, use_flag__exact=0)

            if len(aircraft) > 0:
                aircraft_list = []
                # create a list of dicts with the link to the data page and the image together in an entry
                for entry in aircraft:
                    aircraft_list.append({'data_link': '/data/' + str(entry.image_id),
                                          'image': aircraft_static_location(entry),
                                          'author': entry.author})

                page_vars['aircraft_images'] = convert_image_list_to_rows(aircraft_list[:180])

            else:
                page_vars['error'] = 'Sorry, no images are available for {}.'.format(requested_aircraft)
    else:
        page_vars['error'] = 'Only admins can use the management page.'

    return render(request, 'AircraftSpotter/data_manager.html', page_vars)


def history(request):

    page_vars = {}

    if request.user.is_authenticated():
        try:
            user_history = UserHistory.objects.get(user_id=request.user.pk).get_aircraft_history()

            # transform the plane IDs into the full images to display in the template
            for i, data in enumerate(user_history):
                image_id = data[0]
                success_status = data[1]
                print(data, image_id, success_status)
                user_history[i] = {
                    "image": aircraft_static_location(Aircraft.objects.get(pk=image_id)),
                    "success": success_status[:success_status.find('!')],
                    "correct_aircraft": success_status[success_status.find('!') + 1:]
                }
            user_history = convert_image_list_to_rows(user_history)
            print(user_history)
            page_vars['user_history'] = user_history

        except UserHistory.DoesNotExist:
            page_vars['error'] = 'You have no history.  Try testing a few planes!'
    else:
        page_vars['error'] = 'You must be logged in to view your history.'

    return render(request, 'AircraftSpotter/test_history.html', page_vars)
