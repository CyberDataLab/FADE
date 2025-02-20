# Create your views here.
from django.shortcuts import render
import csv
from django.core.files.base import ContentFile
from io import StringIO
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Scenario, File, AnomalyDetector, Metric
from accounts.models import CustomUser
from .serializers import ScenarioSerializer
from django.http import JsonResponse
from .models import DataController, DataReceiver, DataFilter, DataStorage, DataMixer, DataSync
import logging
import json
import pandas as pd
from sklearn.preprocessing import StandardScaler, MinMaxScaler, OneHotEncoder, Normalizer
from sklearn.impute import KNNImputer
from sklearn.decomposition import PCA
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score, confusion_matrix

logger = logging.getLogger('backend')

def put_data_controller(request):
    controller = DataController(name='Example Controller')
    controller.put_data() 
    return JsonResponse({'message': 'Data has been put successfully'})

def sync_data_controller(request):
    controller = DataController(name='Example Controller')
    controller.sync_data()
    return JsonResponse({'message': 'Data has been synchronized'})

def set_aggregation_technique(request, technique):
    controller = DataController(name='Example Controller')
    controller.set_aggregation_technique(technique)
    return JsonResponse({'message': f'Aggregation technique {technique} has been set'})

def set_filtering_strategy_controller(request, strategy):
    controller = DataController(name='Example Controller')
    controller.set_filtering_strategy(strategy)
    return JsonResponse({'message': f'Filtering strategy {strategy} has been set'})


# View for DataReceiver
def put_data_receiver(request):
    receiver = DataReceiver(name='Example Receiver')
    data = request.POST.get('data', '')
    receiver.put_data(data)
    return JsonResponse({'message': 'Data received by DataReceiver'})

def validate_data_receiver(request):
    receiver = DataReceiver(name='Example Receiver')
    data = request.POST.get('data', '')
    receiver.validate_data(data)
    return JsonResponse({'message': 'Data validated by DataReceiver'})


# View for DataFilter
def set_filtering_strategy_filter(request, strategy):
    data_filter = DataFilter(name='Example Filter')
    data_filter.set_filtering_strategy(strategy)
    return JsonResponse({'message': f'Filtering strategy {strategy} has been set by DataFilter'})

def filter_data(request):
    data_filter = DataFilter(name='Example Filter')
    data = request.POST.get('data', '')
    data_filter.filter_data(data)
    return JsonResponse({'message': 'Data has been filtered'})


# View for DataStorage
def serialize_data(request):
    storage = DataStorage(name='Example Storage')
    data = request.POST.get('data', '')
    storage.serialize_data(data)
    return JsonResponse({'message': 'Data has been serialized'})

def store_data(request):
    storage = DataStorage(name='Example Storage')
    data = request.POST.get('data', '')
    storage.store_data(data)
    return JsonResponse({'message': 'Data has been stored'})

def get_available_space(request):
    storage = DataStorage(name='Example Storage')
    storage.get_available_space()
    return JsonResponse({'message': 'Available space retrieved'})


# View for para DataMixer
def set_aggregation_technique_mixer(request, technique):
    mixer = DataMixer(name='Example Mixer')
    mixer.set_aggregation_technique(technique)
    return JsonResponse({'message': f'Aggregation technique {technique} has been set by DataMixer'})

def check_for_data_to_aggregate(request):
    mixer = DataMixer(name='Example Mixer')
    mixer.check_for_data_to_aggregate()
    return JsonResponse({'message': 'Checked for data to aggregate'})

def aggregate_data(request):
    mixer = DataMixer(name='Example Mixer')
    data_list = request.POST.getlist('data')
    mixer.aggregate_data(data_list)
    return JsonResponse({'message': 'Data has been aggregated'})


# View for para DataSync
def check_sync_status(request):
    sync = DataSync(name='Example Sync')
    sync.check_sync_status()
    return JsonResponse({'message': 'Sync status checked'})

def sync_data_sync(request):
    sync = DataSync(name='Example Sync')
    sync.sync()
    return JsonResponse({'message': 'Data has been synchronized'})

def verify_sync_data(request):
    sync = DataSync(name='Example Sync')
    sync.verify_sync_data()
    return JsonResponse({'message': 'Sync data verified'})

# Views for Scenarios management

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def create_scenario(request):
    user = request.user  
    data = request.data.dict() 
    data['user'] = user.id 

    csv_file = request.FILES.get('csv_file')

    logger.info(csv_file)

    if not csv_file:
        return JsonResponse({"error": "At least one CSV file is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        csv_content = csv_file.read().decode('utf-8')
        csv_reader = csv.reader(StringIO(csv_content))
        entry_count = sum(1 for _ in csv_reader) - 1  
    except Exception as e:
        return JsonResponse({"error": f"Error while reading the CSV file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    file_instance = File.objects.create(
        name=csv_file.name,
        file_type='csv', 
        entry_count=entry_count,
        content=ContentFile(csv_content.encode('utf-8'), name=csv_file.name) 
    )

    logger.info(file_instance)

    data['file'] = file_instance.id
    serializer = ScenarioSerializer(data=data)

    if serializer.is_valid():
        serializer.save(user=user)
        return JsonResponse(serializer.data, status=status.HTTP_201_CREATED)
    
    return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenarios_by_user(request):
    user = request.user  

    scenarios = Scenario.objects.filter(user=user.id)

    serializer = ScenarioSerializer(scenarios, many=True)
    
    return JsonResponse(serializer.data, safe=False, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenario_by_uuid(request, uuid):
    user = request.user 

    try:
        scenario = Scenario.objects.get(uuid=uuid, user=user.id)
        serializer = ScenarioSerializer(scenario)  
        return JsonResponse(serializer.data, safe=False, status=status.HTTP_200_OK) 
    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found or you do not have permission to access it'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenario_metrics_by_uuid(request, uuid):
    try:
        scenario = Scenario.objects.get(uuid=uuid)
        detector = AnomalyDetector.objects.get(scenario=scenario)
        metrics = Metric.objects.filter(detector=detector).order_by('-date')

        metrics_data = [
            {
                "model_name": metric.model_name,
                "accuracy": metric.accuracy,
                "precision": metric.precision,
                "recall": metric.recall,
                "f1_score": metric.f1_score,
                "confusion_matrix": metric.confusion_matrix,
                "date": metric.date
            }
            for metric in metrics
        ]

        return JsonResponse({"metrics": metrics_data}, safe=False)
    except Scenario.DoesNotExist:
        return JsonResponse({"error": "Scenario not found"}, status=404)
    except AnomalyDetector.DoesNotExist:
        return JsonResponse({"error": "Anomaly detector not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def put_scenario_by_uuid(request, uuid):
    user = request.user

    try:
        scenario = Scenario.objects.get(uuid=uuid, user=user)

        design_json = request.POST.get('design')  
        csv_file = request.FILES.get('csv_file')  

        if not design_json:
            return JsonResponse({'error': 'Design field is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            design = json.loads(design_json)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid design JSON'}, status=status.HTTP_400_BAD_REQUEST)

        scenario.design = design

        serializer = ScenarioSerializer(instance=scenario, data={'design': design}, partial=True)
        if serializer.is_valid():
            serializer.save(user=user)
            return JsonResponse({'message': 'Scenario updated correctly'}, status=status.HTTP_200_OK)
        else:
            logger.error("Serializer errors: %s", serializer.errors)
            return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found or without permits'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_scenario_by_uuid(request, uuid):
    user = request.user  

    try:
        scenario = Scenario.objects.get(uuid=uuid, user=user.id)

        if scenario.file:
            scenario.file.delete()

        anomaly_detector = AnomalyDetector.objects.filter(scenario=scenario).first()
        if anomaly_detector:
            Metric.objects.filter(detector=anomaly_detector).delete()
            anomaly_detector.delete()

        scenario.delete()  

        return JsonResponse({'message': 'Scenario, associated file, anomaly detector, and metrics deleted successfully'}, status=status.HTTP_200_OK)

    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found or you do not have permission to delete it'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def run_scenario_by_uuid(request, uuid):
    user = request.user  

    try:
        scenario = Scenario.objects.get(uuid=uuid, user=user)

        scenario.status = "Running"
        scenario.save()

        anomaly_detector, created = AnomalyDetector.objects.get_or_create(scenario=scenario)

        design = scenario.design
        if isinstance(design, str):  
            design = json.loads(design)

        result = execute_scenario(anomaly_detector, design)

        if result.get('error'):
            return JsonResponse(result, status=status.HTTP_400_BAD_REQUEST)

        scenario.status = 'Finished'
        scenario.save()

        return JsonResponse({
            'message': 'Scenario run successfully'
        }, status=status.HTTP_200_OK)

    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found or without permits to run it'}, status=status.HTTP_404_NOT_FOUND)

    
def execute_scenario(anomaly_detector, design):
    try:
        csv_file_name = None
        scaler_params = None
        minmax_params = None
        encoder_params = None
        pca_params = None
        normalizer_params = None
        knnImputer_params = None 
        knn_params = None
        rf_params = None
        lr_params = None
        svm_params = None
        gb_params = None
        dt_params = None

        metrics = {}

        for element in design.get('elements', []):
            if element.get('type') == 'CSV':
                csv_file_name = element.get('parameters', {}).get('csvFileName')
            if element.get('type') == 'StandardScaler':
                scaler_params = element.get('parameters', {})
            elif element.get('type') == 'MinMaxScaler':
                minmax_params = element.get('parameters', {})
            elif element.get('type') == 'OneHotEncoder':
                encoder_params = element.get('parameters', {})
            elif element.get('type') == 'PCA':
                pca_params = element.get('parameters', {})
            elif element.get('type') == 'Normalizer':
                normalizer_params = element.get('parameters', {})
            elif element.get('type') == 'KNNImputer':
                knnImputer_params = element.get('parameters', {})
            elif element.get('type') == 'KNN':
                knn_params = element.get('parameters', {})
            elif element.get('type') == 'RandomForest':
                rf_params = element.get('parameters', {})
            elif element.get('type') == 'LogisticRegression':
                lr_params = element.get('parameters', {})
            elif element.get('type') == 'SVM':
                svm_params = element.get('parameters', {})
            elif element.get('type') == 'GradientBoosting':
                gb_params = element.get('parameters', {})
            elif element.get('type') == 'DecisionTree':
                dt_params = element.get('parameters', {})

        logger.info(csv_file_name)
        logger.info(scaler_params)
        logger.info(rf_params)

        try:
            file = File.objects.get(name=csv_file_name)
        except File.DoesNotExist:
            return {'error': 'CSV file not found'}
    
        logger.info(file)

        csv_file_path = file.content  
        df = pd.read_csv(csv_file_path)
        logger.info(df)

        if scaler_params:
            df_numeric = df.iloc[:, :-1]  
            scaler = StandardScaler(with_std=scaler_params.get('withStd') == 'True', 
                                    with_mean=scaler_params.get('withMean') == 'True')

            df.iloc[:, :-1] = scaler.fit_transform(df_numeric)

        logger.info("LLEGO")

        if minmax_params:
            min_value = float(minmax_params.get('minValue', 0))
            max_value = float(minmax_params.get('maxValue', 1))
            clip = minmax_params.get('clip') == 'False'
            scaler = MinMaxScaler(feature_range=(min_value, max_value), clip=clip)
            df = pd.DataFrame(scaler.fit_transform(df), columns=df.columns)

        if encoder_params:
            df_categorical = df.select_dtypes(include=['object', 'category'])

            handle_unknown = encoder_params.get('handleUnknown', 'error')  
            drop = encoder_params.get('drop', None)  

            encoder = OneHotEncoder(handle_unknown=handle_unknown, drop=drop, sparse_output=False)
            df_encoded = encoder.fit_transform(df_categorical)

            encoded_columns = encoder.get_feature_names_out(df_categorical.columns)
            df_encoded = pd.DataFrame(df_encoded, columns=encoded_columns, index=df.index)

            df = df.drop(columns=df_categorical.columns).join(df_encoded)

        if pca_params:
            df_numeric = df.select_dtypes(include=['float64', 'int64'])

            components_option = pca_params.get('componentsOption', 'None')  
            custom_components = int(pca_params.get('customComponents', 1))  
            whiten = pca_params.get('whiten', 'False') == 'True' 

            if components_option == 'custom':
                n_components = custom_components
            else:
                n_components = None  

            pca = PCA(n_components=n_components, whiten=whiten)
            df_pca = pca.fit_transform(df_numeric)

            pca_columns = [f'PC{i+1}' for i in range(df_pca.shape[1])]
            df_pca = pd.DataFrame(df_pca, columns=pca_columns, index=df.index)

            df = df.drop(columns=df_numeric.columns).join(df_pca)

        if normalizer_params:
            df_numeric = df.select_dtypes(include=['float64', 'int64'])

            norm_type = normalizer_params.get('norm', 'l2') 

            normalizer = Normalizer(norm=norm_type)
            df_normalized = normalizer.fit_transform(df_numeric)

            df_normalized = pd.DataFrame(df_normalized, columns=df_numeric.columns, index=df.index)

            df[df_numeric.columns] = df_normalized
            
        if knnImputer_params:
            df_numeric = df.select_dtypes(include=['float64', 'int64'])

            n_neighbors = int(knnImputer_params.get('neighbors', 5)) 
            weights = knnImputer_params.get('weight', 'uniform') 

            imputer = KNNImputer(n_neighbors=n_neighbors, weights=weights)
            df_imputed = imputer.fit_transform(df_numeric)

            df_imputed = pd.DataFrame(df_imputed, columns=df_numeric.columns, index=df.index)

            df[df_numeric.columns] = df_imputed

        X = df.iloc[:, :-1]  
        y = df.iloc[:, -1]   

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        logger.info("COMIENZO MODELO")
        if knn_params:
            n_neighbors = int(knn_params.get('neighbors', 5))
            weights = knn_params.get('weight', 'uniform')
            algorithm = knn_params.get('algorithm', 'auto')
            metric = knn_params.get('metric', 'minkowski')

            knn = KNeighborsClassifier(n_neighbors=n_neighbors, weights=weights, algorithm=algorithm, metric=metric)
            knn.fit(X_train, y_train)

            y_pred_knn = knn.predict(X_test)

            f1 = f1_score(y_test, y_pred_knn, average='weighted')
            logger.info(f"KNN Model - F1 Score: {f1:.2f}")
            metrics['KNN'] = {
                'f1_score': round(f1, 2)
            }

        if rf_params:
            n_estimators = int(rf_params.get('trees', 100))
            max_depth_option = rf_params.get('depthOption', 'None')
            max_depth = None if max_depth_option == 'None' else int(rf_params.get('customDepth', 1))

            random_state_option = rf_params.get('randomStateOption', 'None')
            if random_state_option == 'None':
                random_state = None
            elif random_state_option == 'custom':
                random_state = int(rf_params.get('customRandomState', 0))
            else:
                random_state = None
            max_features_option = rf_params.get('maxFeaturesOption', 'sqrt')
            if max_features_option == 'custom':
                max_features = int(rf_params.get('customMaxFeatures', 1))
            else:
                max_features = max_features_option

            logger.info("DENTRO RF")

            rf = RandomForestClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                random_state=random_state,
                max_features=max_features
            )

            rf.fit(X_train, y_train)

            y_pred = rf.predict(X_test)

            f1_rf = f1_score(y_test, y_pred, average='weighted') 
            precision_rf = precision_score(y_test, y_pred, average='weighted')
            recall_rf = recall_score(y_test, y_pred, average='weighted')
            accuracy_rf = accuracy_score(y_test, y_pred)
            conf_matrix_rf = confusion_matrix(y_test, y_pred)

            logger.info(f"RandomForest Model - F1 Score: {f1_rf:.2f}")
            logger.info(f"RandomForest Model - Precision: {precision_rf:.2f}")
            logger.info(f"RandomForest Model - Recall: {recall_rf:.2f}")
            logger.info(f"RandomForest Model - Accuracy: {accuracy_rf:.2f}")
            logger.info(f"RandomForest Model - Confusion Matrix:\n{conf_matrix_rf}")

            metrics_rf = {
                'f1_score': round(f1_rf, 2),
                'precision': round(precision_rf, 2),
                'recall': round(recall_rf, 2),
                'accuracy': round(accuracy_rf, 2),
                'confusion_matrix': conf_matrix_rf.tolist()
            }

            Metric.objects.create(
                detector=anomaly_detector,
                model_name='RandomForest',
                accuracy=metrics_rf['accuracy'],
                precision=metrics_rf['precision'],
                recall=metrics_rf['recall'],
                f1_score=metrics_rf['f1_score'],
                confusion_matrix=json.dumps(metrics_rf['confusion_matrix'])
            )

        if lr_params:
            c = float(lr_params.get('c', 1.0))
            penalty = lr_params.get('penalty', 'l2')
            solver = lr_params.get('solver', 'lbfgs')
            max_iter = int(lr_params.get('maxIter', 100))

            lr = LogisticRegression(
                C=c,
                penalty=penalty,
                solver=solver,
                max_iter=max_iter
            )

            lr.fit(X_train, y_train)

            y_pred = lr.predict(X_test)

            f1 = f1_score(y_test, y_pred, average='weighted')
            logger.info(f"Logistic Regression Model - F1 Score: {f1:.2f}")
            metrics['LogisticRegression'] = {
                'f1_score': round(f1, 2)
            }

        if gb_params:
            n_estimators = int(gb_params.get('n_estimators', 100))
            learning_rate = float(gb_params.get('learning_rate', 0.1))
            
            max_depth_option = gb_params.get('max_depth', 'None')
            max_depth = None if max_depth_option == 'None' else int(gb_params.get('customMaxDepth', 3))
            
            random_state_option = gb_params.get('random_state', 'None')
            if random_state_option == 'None':
                random_state = None
            elif random_state_option == 'custom':
                random_state = int(gb_params.get('customRandomState', 0))
            else:
                random_state = None

            gb = GradientBoostingClassifier(
                n_estimators=n_estimators,
                learning_rate=learning_rate,
                max_depth=max_depth,
                random_state=random_state
            )

            gb.fit(X_train, y_train)

            y_pred = gb.predict(X_test)

            f1 = f1_score(y_test, y_pred, average='weighted')
            logger.info(f"Gradient Boosting Model - F1 Score: {f1:.2f}")
            metrics['GradientBoosting'] = {
                'f1_score': round(f1, 2)
            }

        if dt_params:
            criterion = dt_params.get('criterion', 'gini')
            splitter = dt_params.get('splitter', 'best')
            
            max_depth_option = dt_params.get('max_depth', 'None')
            max_depth = None if max_depth_option == 'None' else int(dt_params.get('customMaxDepth', 1))
            
            max_features_option = dt_params.get('max_features', 'None')
            max_features = None if max_features_option == 'None' else int(dt_params.get('customMaxFeatures', 1))
            
            random_state_option = dt_params.get('random_state', 'None')
            if random_state_option == 'None':
                random_state = None
            elif random_state_option == 'custom':
                random_state = int(dt_params.get('customRandomState', 0))
            else:
                random_state = None

            dt = DecisionTreeClassifier(
                criterion=criterion,
                splitter=splitter,
                max_depth=max_depth,
                max_features=max_features,
                random_state=random_state
            )

            dt.fit(X_train, y_train)

            y_pred = dt.predict(X_test)

            f1 = f1_score(y_test, y_pred, average='weighted')
            logger.info(f"Decision Tree Model - F1 Score: {f1:.2f}")
            metrics['DecisionTree'] = {
                'f1_score': round(f1, 2)
            }

        return {'message': 'Model trained successfully', 'metrics': metrics}

    except Exception as e:
        return {'error': str(e)}
    