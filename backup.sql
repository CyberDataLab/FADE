-- MySQL dump 10.13  Distrib 8.0.42, for Linux (aarch64)
--
-- Host: localhost    Database: defender
-- ------------------------------------------------------
-- Server version	8.0.42

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `AnomalyDetector`
--

DROP TABLE IF EXISTS `AnomalyDetector`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `AnomalyDetector` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `scenario_id` bigint DEFAULT NULL,
  `execution` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `AnomalyDetector_scenario_id_e05d3066_fk_Scenario_id` (`scenario_id`),
  CONSTRAINT `AnomalyDetector_scenario_id_e05d3066_fk_Scenario_id` FOREIGN KEY (`scenario_id`) REFERENCES `Scenario` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `AnomalyDetector`
--

LOCK TABLES `AnomalyDetector` WRITE;
/*!40000 ALTER TABLE `AnomalyDetector` DISABLE KEYS */;
INSERT INTO `AnomalyDetector` VALUES (1,34,1);
/*!40000 ALTER TABLE `AnomalyDetector` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `AnomalyMetric`
--

DROP TABLE IF EXISTS `AnomalyMetric`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `AnomalyMetric` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `execution` int NOT NULL,
  `model_name` varchar(255) NOT NULL,
  `feature_name` varchar(255) NOT NULL,
  `anomalies` json NOT NULL,
  `date` datetime(6) NOT NULL,
  `detector_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `AnomalyMetric_detector_id_1eba2ee8_fk_AnomalyDetector_id` (`detector_id`),
  CONSTRAINT `AnomalyMetric_detector_id_1eba2ee8_fk_AnomalyDetector_id` FOREIGN KEY (`detector_id`) REFERENCES `AnomalyDetector` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `AnomalyMetric`
--

LOCK TABLES `AnomalyMetric` WRITE;
/*!40000 ALTER TABLE `AnomalyMetric` DISABLE KEYS */;
INSERT INTO `AnomalyMetric` VALUES (1,1,'IsolationForest','protocol','{\"values\": [1, 0, -1, 1, -1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1], \"anomaly_indices\": [0, 1, 2, 3, 4, 8, 26, 29, 30, 32, 33, 34, 39]}','2025-04-30 14:40:44.598645',1),(2,1,'IsolationForest','packet_count','{\"values\": [4.966654292109234, 3.498515298272462, -0.2766992573078078, 0.004943733346593227, -0.2766992573078078, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, 0.8139182809709367, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2766992573078078, -0.2707068532513312, -0.2707068532513312, -0.14486636806532224, -0.2047904086300884, -0.1987980045736118, -0.1987980045736118, -0.1987980045736118, -0.1928056005171352, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2707068532513312, -0.2766992573078078], \"anomaly_indices\": [0, 1, 2, 3, 4, 8, 26, 29, 30, 32, 33, 34, 39]}','2025-04-30 14:40:44.602422',1),(3,1,'IsolationForest','total_bytes','{\"values\": [5.161678476302073, 3.276500833815302, -0.25625916004248717, -0.1438241267401861, -0.25625916004248717, -0.25492845806296527, -0.2552688701972615, -0.25499035117829183, 0.6198812125862605, -0.2548479970130407, -0.25499035117829183, -0.25479229320924673, -0.2549160794398999, -0.2548108611438447, -0.25495321530909587, -0.2534120767374636, -0.2541981193021114, -0.25469945353625684, -0.2548294290784427, -0.2546561283555282, -0.25477991458618143, -0.2547056428477895, -0.2548294290784427, -0.2549222687514326, -0.2549160794398999, -0.2549037008168346, -0.2561106165657033, -0.2549222687514326, -0.2549222687514326, -0.20327865332291775, -0.21453701100082628, -0.2139923515859522, -0.21349101735180673, -0.2133115273173596, -0.21236456265286263, -0.25504605498208577, -0.2555411999046986, -0.2548913221937693, -0.2551017587858797, -0.24885674344942585], \"anomaly_indices\": [0, 1, 2, 3, 4, 8, 26, 29, 30, 32, 33, 34, 39]}','2025-04-30 14:40:44.605334',1),(4,1,'IsolationForest','avg_packet_size','{\"values\": [2.6399217796216994, 2.2959506456960583, -0.8231625870113849, 0.3880087898154481, -0.8231625870113849, -0.5162073817870888, -0.616104046209197, -0.5343704116820176, 1.8206004037602952, -0.49259544292368146, -0.5343704116820176, -0.4762487160182456, -0.5125747758081031, -0.4816976249867242, -0.5234725937450604, -0.07121314936133417, -0.30188362902692945, -0.4490041711758525, -0.48714653395520285, -0.4362900502494023, -0.4726161100392598, -0.4508204741653453, -0.48714653395520285, -0.5143910787975959, -0.5125747758081031, -0.5089421698291173, -0.7359800435157269, -0.5143910787975959, -0.5143910787975959, 0.3689639316575046, 0.906237290214986, 0.7936065454929166, 0.8146237657999057, 0.8221484496135192, 0.7383736364886239, -0.5507171385874535, -0.6960213777468836, -0.5053095638501316, -0.5670638654928893, 3.5214341638555746], \"anomaly_indices\": [0, 1, 2, 3, 4, 8, 26, 29, 30, 32, 33, 34, 39]}','2025-04-30 14:40:44.607345',1),(5,1,'IsolationForest','flow_duration','{\"values\": [3.761196922938475, 3.8564027470621554, -0.4803745898766156, 2.666339255850521, -0.4803745898766156, -0.3090346443507327, -0.311291676298971, -0.3553744543826899, 0.5774089119469955, -0.26494131455472486, -0.2583541495379487, -0.2895259766027003, -0.28558604999253423, -0.2801901939828124, -0.273557925568409, -0.3185855991427874, -0.3181140824308949, -0.2939254199382342, -0.28163867511487, -0.3004252747082273, -0.30113513598005837, -0.28951108006770415, -0.28971052811959724, -0.33511682195846143, -0.32983889685079265, -0.33418309886904907, -0.4803745898766156, -0.34094571196466894, -0.3326922039915163, -0.1653128747077386, -0.16774514783850122, -0.1662499081382612, -0.16344087680988728, -0.16129494818516202, -0.1458395862303221, -0.30623078543034354, -0.32862400166332767, -0.32061607962129235, -0.320816355258463, -0.4803745898766156], \"anomaly_indices\": [0, 1, 2, 3, 4, 8, 26, 29, 30, 32, 33, 34, 39]}','2025-04-30 14:40:44.608899',1),(6,1,'IsolationForest','avg_ttl','{\"values\": [-0.36741971800536943, -0.3133735211445817, -2.2229668597559353, -0.3803539388627597, -2.2229668597559353, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.3480369380423576, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.21646290844842236, -0.24831217751679557, -0.24831217751679557, 1.3123020068334923, 2.4735753559418696, 2.281429765628278, 2.254130392141101, 2.2950794523718665, 2.127643294983846, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.24831217751679557, -0.21646290844842236], \"anomaly_indices\": [0, 1, 2, 3, 4, 8, 26, 29, 30, 32, 33, 34, 39]}','2025-04-30 14:40:44.610697',1);
/*!40000 ALTER TABLE `AnomalyMetric` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `ClassificationMetric`
--

DROP TABLE IF EXISTS `ClassificationMetric`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ClassificationMetric` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `accuracy` decimal(5,2) DEFAULT NULL,
  `precision` decimal(5,2) DEFAULT NULL,
  `recall` decimal(5,2) DEFAULT NULL,
  `f1_score` decimal(5,2) DEFAULT NULL,
  `confusion_matrix` longtext,
  `date` datetime(6) NOT NULL,
  `detector_id` bigint DEFAULT NULL,
  `model_name` varchar(255) NOT NULL,
  `execution` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `Metric_detector_id_a8c3c16e_fk_AnomalyDetector_id` (`detector_id`),
  CONSTRAINT `Metric_detector_id_a8c3c16e_fk_AnomalyDetector_id` FOREIGN KEY (`detector_id`) REFERENCES `AnomalyDetector` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ClassificationMetric`
--

LOCK TABLES `ClassificationMetric` WRITE;
/*!40000 ALTER TABLE `ClassificationMetric` DISABLE KEYS */;
/*!40000 ALTER TABLE `ClassificationMetric` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `File`
--

DROP TABLE IF EXISTS `File`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `File` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `file_type` varchar(10) NOT NULL,
  `entry_count` int NOT NULL,
  `content` varchar(100) NOT NULL,
  `references` int NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `File`
--

LOCK TABLES `File` WRITE;
/*!40000 ALTER TABLE `File` DISABLE KEYS */;
INSERT INTO `File` VALUES (1,'packets_window.pcap','pcap',0,'files/packets_window_qEZWQfI.pcap',1);
/*!40000 ALTER TABLE `File` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `RegressionMetric`
--

DROP TABLE IF EXISTS `RegressionMetric`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `RegressionMetric` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `execution` int NOT NULL,
  `model_name` varchar(255) NOT NULL,
  `mse` decimal(10,5) DEFAULT NULL,
  `rmse` decimal(10,5) DEFAULT NULL,
  `mae` decimal(10,5) DEFAULT NULL,
  `r2` decimal(5,2) DEFAULT NULL,
  `msle` decimal(10,5) DEFAULT NULL,
  `date` datetime(6) NOT NULL,
  `detector_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `RegressionMetric_detector_id_6256c6fd_fk_AnomalyDetector_id` (`detector_id`),
  CONSTRAINT `RegressionMetric_detector_id_6256c6fd_fk_AnomalyDetector_id` FOREIGN KEY (`detector_id`) REFERENCES `AnomalyDetector` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `RegressionMetric`
--

LOCK TABLES `RegressionMetric` WRITE;
/*!40000 ALTER TABLE `RegressionMetric` DISABLE KEYS */;
/*!40000 ALTER TABLE `RegressionMetric` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `Scenario`
--

DROP TABLE IF EXISTS `Scenario`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Scenario` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `design` json NOT NULL,
  `date` datetime(6) NOT NULL,
  `user_id` bigint NOT NULL,
  `status` varchar(255) NOT NULL,
  `uuid` char(32) NOT NULL,
  `file_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `Scenario_user_id_31ea73d4_fk_User_id` (`user_id`),
  KEY `Scenario_file_id_e186ee4b_fk_File_id` (`file_id`),
  CONSTRAINT `Scenario_file_id_e186ee4b_fk_File_id` FOREIGN KEY (`file_id`) REFERENCES `File` (`id`),
  CONSTRAINT `Scenario_user_id_31ea73d4_fk_User_id` FOREIGN KEY (`user_id`) REFERENCES `User` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=35 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `Scenario`
--

LOCK TABLES `Scenario` WRITE;
/*!40000 ALTER TABLE `Scenario` DISABLE KEYS */;
INSERT INTO `Scenario` VALUES (34,'prueba','\"{\\\"elements\\\":[{\\\"id\\\":\\\"72c819188e218617\\\",\\\"type\\\":\\\"Network\\\",\\\"position\\\":{\\\"left\\\":-223,\\\"top\\\":-12},\\\"parameters\\\":{\\\"networkFileName\\\":\\\"packets_window.pcap\\\"}},{\\\"id\\\":\\\"ea4bd13dc26340c7\\\",\\\"type\\\":\\\"StandardScaler\\\",\\\"position\\\":{\\\"left\\\":58,\\\"top\\\":-52},\\\"parameters\\\":{\\\"with_std\\\":\\\"True\\\",\\\"with_mean\\\":\\\"True\\\"}},{\\\"id\\\":\\\"67c75bd1825e4cb0\\\",\\\"type\\\":\\\"IsolationForest\\\",\\\"position\\\":{\\\"left\\\":320,\\\"top\\\":-44},\\\"parameters\\\":{\\\"n_estimators\\\":100,\\\"max_samples\\\":\\\"auto\\\",\\\"contamination\\\":\\\"auto\\\",\\\"max_features\\\":1,\\\"random_state\\\":\\\"None\\\"}}],\\\"connections\\\":[{\\\"startId\\\":\\\"ea4bd13dc26340c7\\\",\\\"endId\\\":\\\"67c75bd1825e4cb0\\\"},{\\\"startId\\\":\\\"72c819188e218617\\\",\\\"endId\\\":\\\"ea4bd13dc26340c7\\\"}]}\"','2025-04-30 14:40:33.132560',13,'Finished','65e53285a5fe464884cf518999b8fbe2',1);
/*!40000 ALTER TABLE `Scenario` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `User`
--

DROP TABLE IF EXISTS `User`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `User` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(255) NOT NULL,
  `last_name` varchar(255) NOT NULL,
  `email` varchar(254) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  `admin_username` varchar(255) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=27 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `User`
--

LOCK TABLES `User` WRITE;
/*!40000 ALTER TABLE `User` DISABLE KEYS */;
INSERT INTO `User` VALUES (13,'pbkdf2_sha256$600000$baHBUnfwlIb0NtEDc2NfXx$RbDxZaiPmho/tRTGqAuB8C7MCPcRNCoJmTFQ+Iv2bko=','2025-02-11 09:52:07.217930',0,'edulb96','Eduardo','Lopez','eduardo.lopez5@um.es',1,1,'2024-11-04 18:12:59.235976','edulb96'),(26,'pbkdf2_sha256$600000$VLSoHgiwx49bMj81kjhIuh$qpSpuLJnRqgrMCKhOvdYrygcI19/xTezX4G3IuuCgsU=','2025-02-11 09:50:06.851474',0,'defender2025','Defender','Project','edulb96@gmail.es',0,1,'2025-02-06 08:45:52.280361','edulb96');
/*!40000 ALTER TABLE `User` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `User_groups`
--

DROP TABLE IF EXISTS `User_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `User_groups` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `customuser_id` bigint NOT NULL,
  `group_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `accounts_customuser_groups_customuser_id_group_id_c074bdcb_uniq` (`customuser_id`,`group_id`),
  KEY `accounts_customuser_groups_group_id_86ba5f9e_fk_auth_group_id` (`group_id`),
  CONSTRAINT `accounts_customuser__customuser_id_bc55088e_fk_accounts_` FOREIGN KEY (`customuser_id`) REFERENCES `User` (`id`),
  CONSTRAINT `accounts_customuser_groups_group_id_86ba5f9e_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `User_groups`
--

LOCK TABLES `User_groups` WRITE;
/*!40000 ALTER TABLE `User_groups` DISABLE KEYS */;
/*!40000 ALTER TABLE `User_groups` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `User_user_permissions`
--

DROP TABLE IF EXISTS `User_user_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `User_user_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `customuser_id` bigint NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `accounts_customuser_user_customuser_id_permission_9632a709_uniq` (`customuser_id`,`permission_id`),
  KEY `accounts_customuser__permission_id_aea3d0e5_fk_auth_perm` (`permission_id`),
  CONSTRAINT `accounts_customuser__customuser_id_0deaefae_fk_accounts_` FOREIGN KEY (`customuser_id`) REFERENCES `User` (`id`),
  CONSTRAINT `accounts_customuser__permission_id_aea3d0e5_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `User_user_permissions`
--

LOCK TABLES `User_user_permissions` WRITE;
/*!40000 ALTER TABLE `User_user_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `User_user_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `action_execution_actioncontroller`
--

DROP TABLE IF EXISTS `action_execution_actioncontroller`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `action_execution_actioncontroller` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `action_execution_actioncontroller`
--

LOCK TABLES `action_execution_actioncontroller` WRITE;
/*!40000 ALTER TABLE `action_execution_actioncontroller` DISABLE KEYS */;
/*!40000 ALTER TABLE `action_execution_actioncontroller` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `action_execution_actionreceiver`
--

DROP TABLE IF EXISTS `action_execution_actionreceiver`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `action_execution_actionreceiver` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `action_execution_actionreceiver`
--

LOCK TABLES `action_execution_actionreceiver` WRITE;
/*!40000 ALTER TABLE `action_execution_actionreceiver` DISABLE KEYS */;
/*!40000 ALTER TABLE `action_execution_actionreceiver` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `action_execution_actionsync`
--

DROP TABLE IF EXISTS `action_execution_actionsync`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `action_execution_actionsync` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `action_execution_actionsync`
--

LOCK TABLES `action_execution_actionsync` WRITE;
/*!40000 ALTER TABLE `action_execution_actionsync` DISABLE KEYS */;
/*!40000 ALTER TABLE `action_execution_actionsync` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `action_execution_performaction`
--

DROP TABLE IF EXISTS `action_execution_performaction`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `action_execution_performaction` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `action_execution_performaction`
--

LOCK TABLES `action_execution_performaction` WRITE;
/*!40000 ALTER TABLE `action_execution_performaction` DISABLE KEYS */;
/*!40000 ALTER TABLE `action_execution_performaction` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `action_execution_policymanagement`
--

DROP TABLE IF EXISTS `action_execution_policymanagement`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `action_execution_policymanagement` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `action_execution_policymanagement`
--

LOCK TABLES `action_execution_policymanagement` WRITE;
/*!40000 ALTER TABLE `action_execution_policymanagement` DISABLE KEYS */;
/*!40000 ALTER TABLE `action_execution_policymanagement` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_group`
--

DROP TABLE IF EXISTS `auth_group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(150) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group`
--

LOCK TABLES `auth_group` WRITE;
/*!40000 ALTER TABLE `auth_group` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_group_permissions`
--

DROP TABLE IF EXISTS `auth_group_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `group_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group_permissions`
--

LOCK TABLES `auth_group_permissions` WRITE;
/*!40000 ALTER TABLE `auth_group_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_permission`
--

DROP TABLE IF EXISTS `auth_permission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_permission` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `content_type_id` int NOT NULL,
  `codename` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`),
  CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=101 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_permission`
--

LOCK TABLES `auth_permission` WRITE;
/*!40000 ALTER TABLE `auth_permission` DISABLE KEYS */;
INSERT INTO `auth_permission` VALUES (1,'Can add log entry',1,'add_logentry'),(2,'Can change log entry',1,'change_logentry'),(3,'Can delete log entry',1,'delete_logentry'),(4,'Can view log entry',1,'view_logentry'),(5,'Can add permission',2,'add_permission'),(6,'Can change permission',2,'change_permission'),(7,'Can delete permission',2,'delete_permission'),(8,'Can view permission',2,'view_permission'),(9,'Can add group',3,'add_group'),(10,'Can change group',3,'change_group'),(11,'Can delete group',3,'delete_group'),(12,'Can view group',3,'view_group'),(13,'Can add user',4,'add_user'),(14,'Can change user',4,'change_user'),(15,'Can delete user',4,'delete_user'),(16,'Can view user',4,'view_user'),(17,'Can add content type',5,'add_contenttype'),(18,'Can change content type',5,'change_contenttype'),(19,'Can delete content type',5,'delete_contenttype'),(20,'Can view content type',5,'view_contenttype'),(21,'Can add session',6,'add_session'),(22,'Can change session',6,'change_session'),(23,'Can delete session',6,'delete_session'),(24,'Can view session',6,'view_session'),(25,'Can add data controller',7,'add_datacontroller'),(26,'Can change data controller',7,'change_datacontroller'),(27,'Can delete data controller',7,'delete_datacontroller'),(28,'Can view data controller',7,'view_datacontroller'),(29,'Can add data filter',8,'add_datafilter'),(30,'Can change data filter',8,'change_datafilter'),(31,'Can delete data filter',8,'delete_datafilter'),(32,'Can view data filter',8,'view_datafilter'),(33,'Can add data mixer',9,'add_datamixer'),(34,'Can change data mixer',9,'change_datamixer'),(35,'Can delete data mixer',9,'delete_datamixer'),(36,'Can view data mixer',9,'view_datamixer'),(37,'Can add data receiver',10,'add_datareceiver'),(38,'Can change data receiver',10,'change_datareceiver'),(39,'Can delete data receiver',10,'delete_datareceiver'),(40,'Can view data receiver',10,'view_datareceiver'),(41,'Can add data storage',11,'add_datastorage'),(42,'Can change data storage',11,'change_datastorage'),(43,'Can delete data storage',11,'delete_datastorage'),(44,'Can view data storage',11,'view_datastorage'),(45,'Can add data sync',12,'add_datasync'),(46,'Can change data sync',12,'change_datasync'),(47,'Can delete data sync',12,'delete_datasync'),(48,'Can view data sync',12,'view_datasync'),(49,'Can add action controller',13,'add_actioncontroller'),(50,'Can change action controller',13,'change_actioncontroller'),(51,'Can delete action controller',13,'delete_actioncontroller'),(52,'Can view action controller',13,'view_actioncontroller'),(53,'Can add action receiver',14,'add_actionreceiver'),(54,'Can change action receiver',14,'change_actionreceiver'),(55,'Can delete action receiver',14,'delete_actionreceiver'),(56,'Can view action receiver',14,'view_actionreceiver'),(57,'Can add action sync',15,'add_actionsync'),(58,'Can change action sync',15,'change_actionsync'),(59,'Can delete action sync',15,'delete_actionsync'),(60,'Can view action sync',15,'view_actionsync'),(61,'Can add perform action',16,'add_performaction'),(62,'Can change perform action',16,'change_performaction'),(63,'Can delete perform action',16,'delete_performaction'),(64,'Can view perform action',16,'view_performaction'),(65,'Can add policy management',17,'add_policymanagement'),(66,'Can change policy management',17,'change_policymanagement'),(67,'Can delete policy management',17,'delete_policymanagement'),(68,'Can view policy management',17,'view_policymanagement'),(69,'Can add user',18,'add_customuser'),(70,'Can change user',18,'change_customuser'),(71,'Can delete user',18,'delete_customuser'),(72,'Can view user',18,'view_customuser'),(73,'Can add user',19,'add_user'),(74,'Can change user',19,'change_user'),(75,'Can delete user',19,'delete_user'),(76,'Can view user',19,'view_user'),(77,'Can add scenario',20,'add_scenario'),(78,'Can change scenario',20,'change_scenario'),(79,'Can delete scenario',20,'delete_scenario'),(80,'Can view scenario',20,'view_scenario'),(81,'Can add file',21,'add_file'),(82,'Can change file',21,'change_file'),(83,'Can delete file',21,'delete_file'),(84,'Can view file',21,'view_file'),(85,'Can add anomaly detector',22,'add_anomalydetector'),(86,'Can change anomaly detector',22,'change_anomalydetector'),(87,'Can delete anomaly detector',22,'delete_anomalydetector'),(88,'Can view anomaly detector',22,'view_anomalydetector'),(89,'Can add classification metric',23,'add_classificationmetric'),(90,'Can change classification metric',23,'change_classificationmetric'),(91,'Can delete classification metric',23,'delete_classificationmetric'),(92,'Can view classification metric',23,'view_classificationmetric'),(93,'Can add anomaly metric',24,'add_anomalymetric'),(94,'Can change anomaly metric',24,'change_anomalymetric'),(95,'Can delete anomaly metric',24,'delete_anomalymetric'),(96,'Can view anomaly metric',24,'view_anomalymetric'),(97,'Can add regression metric',25,'add_regressionmetric'),(98,'Can change regression metric',25,'change_regressionmetric'),(99,'Can delete regression metric',25,'delete_regressionmetric'),(100,'Can view regression metric',25,'view_regressionmetric');
/*!40000 ALTER TABLE `auth_permission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_user`
--

DROP TABLE IF EXISTS `auth_user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user` (
  `id` int NOT NULL AUTO_INCREMENT,
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(150) NOT NULL,
  `last_name` varchar(150) NOT NULL,
  `email` varchar(254) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user`
--

LOCK TABLES `auth_user` WRITE;
/*!40000 ALTER TABLE `auth_user` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_user_groups`
--

DROP TABLE IF EXISTS `auth_user_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user_groups` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `group_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_groups_user_id_group_id_94350c0c_uniq` (`user_id`,`group_id`),
  KEY `auth_user_groups_group_id_97559544_fk_auth_group_id` (`group_id`),
  CONSTRAINT `auth_user_groups_group_id_97559544_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  CONSTRAINT `auth_user_groups_user_id_6a12ed8b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user_groups`
--

LOCK TABLES `auth_user_groups` WRITE;
/*!40000 ALTER TABLE `auth_user_groups` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user_groups` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_user_user_permissions`
--

DROP TABLE IF EXISTS `auth_user_user_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user_user_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_user_permissions_user_id_permission_id_14a6b632_uniq` (`user_id`,`permission_id`),
  KEY `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user_user_permissions`
--

LOCK TABLES `auth_user_user_permissions` WRITE;
/*!40000 ALTER TABLE `auth_user_user_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user_user_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `data_management_datacontroller`
--

DROP TABLE IF EXISTS `data_management_datacontroller`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `data_management_datacontroller` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `data_management_datacontroller`
--

LOCK TABLES `data_management_datacontroller` WRITE;
/*!40000 ALTER TABLE `data_management_datacontroller` DISABLE KEYS */;
/*!40000 ALTER TABLE `data_management_datacontroller` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `data_management_datafilter`
--

DROP TABLE IF EXISTS `data_management_datafilter`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `data_management_datafilter` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `data_management_datafilter`
--

LOCK TABLES `data_management_datafilter` WRITE;
/*!40000 ALTER TABLE `data_management_datafilter` DISABLE KEYS */;
/*!40000 ALTER TABLE `data_management_datafilter` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `data_management_datamixer`
--

DROP TABLE IF EXISTS `data_management_datamixer`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `data_management_datamixer` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `data_management_datamixer`
--

LOCK TABLES `data_management_datamixer` WRITE;
/*!40000 ALTER TABLE `data_management_datamixer` DISABLE KEYS */;
/*!40000 ALTER TABLE `data_management_datamixer` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `data_management_datareceiver`
--

DROP TABLE IF EXISTS `data_management_datareceiver`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `data_management_datareceiver` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `data_management_datareceiver`
--

LOCK TABLES `data_management_datareceiver` WRITE;
/*!40000 ALTER TABLE `data_management_datareceiver` DISABLE KEYS */;
/*!40000 ALTER TABLE `data_management_datareceiver` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `data_management_datastorage`
--

DROP TABLE IF EXISTS `data_management_datastorage`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `data_management_datastorage` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `data_management_datastorage`
--

LOCK TABLES `data_management_datastorage` WRITE;
/*!40000 ALTER TABLE `data_management_datastorage` DISABLE KEYS */;
/*!40000 ALTER TABLE `data_management_datastorage` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `data_management_datasync`
--

DROP TABLE IF EXISTS `data_management_datasync`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `data_management_datasync` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `data_management_datasync`
--

LOCK TABLES `data_management_datasync` WRITE;
/*!40000 ALTER TABLE `data_management_datasync` DISABLE KEYS */;
/*!40000 ALTER TABLE `data_management_datasync` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_admin_log`
--

DROP TABLE IF EXISTS `django_admin_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_admin_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext,
  `object_repr` varchar(200) NOT NULL,
  `action_flag` smallint unsigned NOT NULL,
  `change_message` longtext NOT NULL,
  `content_type_id` int DEFAULT NULL,
  `user_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  CONSTRAINT `django_admin_log_chk_1` CHECK ((`action_flag` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_admin_log`
--

LOCK TABLES `django_admin_log` WRITE;
/*!40000 ALTER TABLE `django_admin_log` DISABLE KEYS */;
/*!40000 ALTER TABLE `django_admin_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_content_type`
--

DROP TABLE IF EXISTS `django_content_type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_content_type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) NOT NULL,
  `model` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`)
) ENGINE=InnoDB AUTO_INCREMENT=26 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_content_type`
--

LOCK TABLES `django_content_type` WRITE;
/*!40000 ALTER TABLE `django_content_type` DISABLE KEYS */;
INSERT INTO `django_content_type` VALUES (18,'accounts','customuser'),(19,'accounts','user'),(13,'action_execution','actioncontroller'),(14,'action_execution','actionreceiver'),(15,'action_execution','actionsync'),(16,'action_execution','performaction'),(17,'action_execution','policymanagement'),(1,'admin','logentry'),(3,'auth','group'),(2,'auth','permission'),(4,'auth','user'),(5,'contenttypes','contenttype'),(22,'data_management','anomalydetector'),(24,'data_management','anomalymetric'),(23,'data_management','classificationmetric'),(7,'data_management','datacontroller'),(8,'data_management','datafilter'),(9,'data_management','datamixer'),(10,'data_management','datareceiver'),(11,'data_management','datastorage'),(12,'data_management','datasync'),(21,'data_management','file'),(25,'data_management','regressionmetric'),(20,'data_management','scenario'),(6,'sessions','session');
/*!40000 ALTER TABLE `django_content_type` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_migrations`
--

DROP TABLE IF EXISTS `django_migrations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_migrations` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `app` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=46 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_migrations`
--

LOCK TABLES `django_migrations` WRITE;
/*!40000 ALTER TABLE `django_migrations` DISABLE KEYS */;
INSERT INTO `django_migrations` VALUES (1,'contenttypes','0001_initial','2024-10-17 17:11:44.441187'),(2,'auth','0001_initial','2024-10-17 17:11:44.649390'),(6,'contenttypes','0002_remove_content_type_name','2024-10-17 17:11:44.734800'),(7,'auth','0002_alter_permission_name_max_length','2024-10-17 17:11:44.758061'),(8,'auth','0003_alter_user_email_max_length','2024-10-17 17:11:44.769907'),(9,'auth','0004_alter_user_username_opts','2024-10-17 17:11:44.773757'),(10,'auth','0005_alter_user_last_login_null','2024-10-17 17:11:44.792801'),(11,'auth','0006_require_contenttypes_0002','2024-10-17 17:11:44.794251'),(12,'auth','0007_alter_validators_add_error_messages','2024-10-17 17:11:44.798533'),(13,'auth','0008_alter_user_username_max_length','2024-10-17 17:11:44.822660'),(14,'auth','0009_alter_user_last_name_max_length','2024-10-17 17:11:44.845913'),(15,'auth','0010_alter_group_name_max_length','2024-10-17 17:11:44.854353'),(16,'auth','0011_update_proxy_permissions','2024-10-17 17:11:44.858629'),(17,'auth','0012_alter_user_first_name_max_length','2024-10-17 17:11:44.880094'),(18,'data_management','0001_initial','2024-10-17 17:11:44.920462'),(20,'action_execution','0001_initial','2024-10-17 17:23:43.492099'),(22,'accounts','0001_initial','2024-11-04 16:13:12.469707'),(23,'admin','0001_initial','2024-11-04 16:19:14.952155'),(24,'admin','0002_logentry_remove_auto_add','2024-11-04 16:19:14.954904'),(25,'admin','0003_logentry_add_action_flag_choices','2024-11-04 16:19:14.956699'),(26,'accounts','0002_rename_customuser_user_alter_user_options_and_more','2024-11-04 16:19:14.958184'),(27,'sessions','0001_initial','2024-11-04 16:19:38.878524'),(28,'accounts','0002_alter_customuser_options_alter_customuser_table','2024-11-04 16:23:47.377663'),(29,'accounts','0003_remove_customuser_lastname_remove_customuser_name_and_more','2024-11-04 16:26:26.062184'),(30,'accounts','0004_customuser_is_verified_customuser_verification_code_and_more','2024-11-04 17:31:44.082807'),(31,'accounts','0005_remove_customuser_is_verified_and_more','2024-11-04 18:02:42.446015'),(32,'accounts','0006_customuser_admin_username_and_more','2024-11-05 08:39:32.169433'),(33,'data_management','0002_scenario','2025-01-28 10:07:29.060433'),(34,'data_management','0003_alter_scenario_name','2025-01-28 12:02:34.316663'),(35,'data_management','0004_scenario_status_scenario_uuid','2025-01-29 11:17:37.432425'),(36,'data_management','0005_file_scenario_file','2025-04-30 14:39:16.658407'),(37,'data_management','0006_anomalydetector_metric','2025-04-30 14:39:16.731091'),(38,'data_management','0007_rename_precission_metric_precision_metric_model_name','2025-04-30 14:39:16.769047'),(39,'data_management','0008_rename_f1score_metric_f1_score','2025-04-30 14:39:16.780582'),(40,'data_management','0009_alter_metric_accuracy_alter_metric_f1_score_and_more','2025-04-30 14:39:16.883604'),(41,'data_management','0010_file_references_alter_file_content','2025-04-30 14:39:16.907121'),(42,'data_management','0011_alter_metric_accuracy_alter_metric_confusion_matrix_and_more','2025-04-30 14:39:16.996579'),(43,'data_management','0012_anomalydetector_execution_metric_execution','2025-04-30 14:39:17.054751'),(44,'data_management','0013_rename_metric_classificationmetric_and_more','2025-04-30 14:39:17.114116'),(45,'data_management','0014_rename_timestamp_anomalymetric_date_regressionmetric','2025-04-30 14:39:17.159270');
/*!40000 ALTER TABLE `django_migrations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_session`
--

DROP TABLE IF EXISTS `django_session`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_session` (
  `session_key` varchar(40) NOT NULL,
  `session_data` longtext NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `django_session_expire_date_a5c62663` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_session`
--

LOCK TABLES `django_session` WRITE;
/*!40000 ALTER TABLE `django_session` DISABLE KEYS */;
INSERT INTO `django_session` VALUES ('0mx90ce28khhjez0s77197tlsgdrcohd','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1t9Qa8:mF5qRoRo6uFwyp0ZtkLmPruQkBp1bUbA4kMSRbxcTt4','2024-11-22 15:07:28.069294'),('0ore9dco8jwhhmnl522vmam7ynr6m07c','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1t9RC4:0RVaythHKrkSy_SS5fV43uYBiOj80jREYfYi67DXQmY','2024-11-22 15:46:40.856683'),('2seqiwuvy70v2erydd31su7t79f9ij9w','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tFxgN:k7XDQTM43yr4da6hvWzGc-sfGRfI6RMUpCXQTWXY5Pw','2024-12-10 15:40:55.536233'),('4im6zrswtlkt1xcbm0y7ppq2cwzo1n27','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tApWA:y-Q6xAU9rCzqm8YM_s67BLcXzfPAAD7wOR5zGv8W9g4','2024-11-26 11:57:10.873715'),('4to4lpndph77pxfngcm32m9rpg77jpyt','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tFxkh:2lLEa4uf7B7kehugbH2l5WTwn-6CFW239Ji7bH3uwiA','2024-12-10 15:45:23.188614'),('5w0nkmx3tif1zwz4a7tn2esbl7w0prou','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tDoXx:IixXuuevppqPfyp1-PbNGoAacLGY2mKTrs6kjpnORRc','2024-12-04 17:31:21.893623'),('9aeo1pih3rs5hx9qi77yq6q62s51orpy','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1t9Qmc:-JfDG-CGsbCXKbN0QJAER8Q3D8rHUOjx5f0p0RntUbs','2024-11-22 15:20:22.647915'),('9afk4584at7ib1uh9481yydxk9zq1kwn','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tM2DD:YKQFWcLLfv9RyqnFyBEi3QfF_H1YNz8cJeJjV2RZYzQ','2024-12-27 09:43:55.578012'),('a0nf82w73f6csjhs04b6azbpg36f3mfl','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tBXRp:X7RW5rvEqy2T_rXJA-IEM3VOwA1kmgk3sN2BcXRPwVA','2024-11-28 10:51:37.756855'),('ab3nb2l5i53ddm1aje5dery5qpsy10ok','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1t9QWy:PvRphscYJtXc3thA3Rhv0nlk996GTg_7CitrQ8hR1Ys','2024-11-22 15:04:12.756986'),('bsasid72aztr07r0hyzvt74fdnez0y2g','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tA3oX:qM7fjYR6DbpqZkpio5nUPF4M4GTLyhhkNCETHIRTbqA','2024-11-24 09:00:57.134828'),('byzbw7ybn5wz0hhcvkzr3kksr66kl5u9','.eJxVjDsOwjAQBe_iGlnGYY1DSZ8zWG-9axJAjpRPhbg7REoB7ZuZ9zIJ69KnddYpDWIuxgdz-B0Z-aF1I3JHvY02j3WZBrabYnc6224UfV539--gx9x_6wYSM4hIPXvikzSAC4RG26IAx4gSWeO5UOsglFVL8BIyXHRHZPP-AD2yOas:1thmu6:CRVYLH-hSZOid-IZVpr7vU-C3pmEFLW9i_zYJCc_ETg','2025-02-25 09:50:06.853537'),('c4l63phnbnb0r7ob7yhk0xzuhvqrdnv3','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tASCW:-TWfg-x4GviVTZOXF1MdS9epdmrkppxuJYtt5Dgwt1A','2024-11-25 11:03:20.825527'),('c70y90lrz77i5qgb2691znywpelxdve1','.eJxVjEsOwjAMBe-SNYriVKlbluw5Q2TXNi2gROpnVXF3VKkL2L6ZebvLtK1j3had8yTu6qB3l9-RaXhpOYg8qTyqH2pZ54n9ofiTLv5eRd-30_07GGkZj1okiqmlnlBjstT0ISJgpKFtwUAoaDBIYIqKAZm6mJiRWUA6adznCyxYOPI:1t8NSl:Z0Odjg82ADzFyMmlmKb-6wEv_xXe5SAgEfMJeRPPpVE','2024-11-19 17:35:31.133116'),('dk9sety67jd76ualerdwo7w2rrn350l0','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tAR1b:GzZRNR1jCn5T72f2lJneYPlkwj75UjmPaau-6EyeIOE','2024-11-25 09:47:59.370675'),('ehgh73y3ub84i43bqlr5kautsrdnx23i','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tAR8W:W-SWGrHNDUxD-Vah0uZNMB2tWZMuLvxpxN-fB3kyOqA','2024-11-25 09:55:08.064885'),('ervc19fg392bjpynkq1nyqhry0vevmzz','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tAS7F:va9pUUeyu1Ur-Bk1NhAUtkRKG74_4pVfwvl6OjVoYKw','2024-11-25 10:57:53.616030'),('ez9y56zklecgdgr7rf4euvdw1x3ng434','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tAR4N:mSJf03W7Wayg7ghVKQB_LtLdTM-IQm7I09tNylJOM6Y','2024-11-25 09:50:51.920585'),('f1ml4in6kuta6zj856jv3ensra0dve61','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1t9QDB:q_7eAXbc00O_RsBTk0rllRrBg8HHp1TARIvCw7oj478','2024-11-22 14:43:45.948805'),('hgm09dmgm6yb2eaotfke7bks56lj1csm','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1thmtr:2MAARDsCxjdDCockwebLCTbGjhEu39LBfT_lfO1sBRo','2025-02-25 09:49:51.461821'),('hy0e4os7ycn8pyi8wbwept69aq3m6u7z','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1t8jYU:2Geuwc6G3WPM4kJpeLHm7QrirrAbiq6M9vkSd64hfLA','2024-11-20 17:10:54.543046'),('i4cslhg9gmdhzc3ofbtxivzim7j62g3x','.eJxVjDEOgzAMAP-SuYogAeN07M4bkGObhrZKJAJT1b9XSAztene6t5lo39K0V12nRczVOG8uvzASPzUfRh6U78Vyydu6RHsk9rTVjkX0dTvbv0Gimo6vMDucBZrIjD3EoLNwQ2GAIUjfduCQqe00ICGCd8McNKIE8soQwXy-Jzo4uw:1t8jn9:4_sMzyXp7kfzt--aFdkBwyTl8SuyoA5Q8wWVFbVJhKQ','2024-11-20 17:26:03.023534'),('kslas1kyugms10gx5dd34vq6ljrarnau','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tFt5j:8eEvqTzwS2RdCAUL5tE4kTUrHM1V6ayv4_rjw5y_GpQ','2024-12-10 10:46:47.930212'),('ml1c4llg062oxd9xpqm0o2ojp8n14uib','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1t8IfB:gtnA77VKc_36l-vc8ByJd-KBBb_dUx0arc1p1MeoG7A','2024-11-19 12:28:01.852143'),('msaqz7aqdomfw5bse4y7uun55ssdg33w','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1thmw3:uKDSsh4Swa4leXybSx-aVoahlIlrqcBfszuE9goFgBQ','2025-02-25 09:52:07.220319'),('q791nvms2zce9hb3ny0710i0da3svtyl','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tDo78:uurkWUE_NHOJ6YtBECmuPpQYy45HvwtzwVy2inHB1vQ','2024-12-04 17:03:38.759892'),('qartx8e9pk1kyi0uk6ngu23zvx2z3que','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1t8jnQ:jIYQdLtjxztZ9Hk1yTZvVd6LS-7MSQR8wxQ7nxI_RcU','2024-11-20 17:26:20.771340'),('qg1i2xag1by0vve36tw290aq0jy8modm','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1t8iGT:LOdGX--_RfUuYCs-kQ92ruD_t2kMtjKCjuGnN1sdQxU','2024-11-20 15:48:13.523054'),('qxuryanivtn81o1yja9xbn1gh9fkwcjn','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tAR5V:7U4k6m2CkeZlWv0mUkussrhYf6g_8EXDv74KkOAmckw','2024-11-25 09:52:01.227697'),('s0w5n9yx9iuas3wbz83l0x04l0jmmkpm','.eJxVjEEOwiAQRe_C2hAyMC116d4zkBkYpGpoUtpV491tky50-997f1OB1qWEtckcxqSuCoy6_I5M8SX1IOlJ9THpONVlHlkfij5p0_cpyft2un8HhVrZazImC_Ye2EIXfRoickIeIEtEsUg-k3XSo5AVIrv7xhmm7BxAl636fAEhszip:1t8jaQ:s8T8Rdi43Se6753VFex1xX7dfPXCGnFbNDqPcV0YZGo','2024-11-20 17:12:54.856050'),('s1f5rg2pfp5yh2guqi8z8gurygfa7jgj','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tAS5t:3PjYwcvq5NWQ9m35ErgPd84ayIcnK-0MUaUQ2fkouuY','2024-11-25 10:56:29.677743'),('te9if4z49z9xlnvfhkijbk4vhboqt14p','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1t8y9K:m1O-Zc6QNqsPIC4O8nWR4Kcmi1UyU5wXTxZjzTmM7M0','2024-11-21 08:45:54.653552'),('tlt7g59zmynur74gpys0xbar5fva1i2k','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tDoP3:OThm17Q5cgtj-WAt_u3V9Gfk6Uj-6h3sHwPz8hqSMQY','2024-12-04 17:22:09.754957'),('u8ua5ywmham8725igkloqb0sbfd4f5tw','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tApah:EBqu_pdPUXWHiypPN9hdLx1KEMW_1l4MAY_FsVXbYcU','2024-11-26 12:01:51.970859'),('w0xbbw712wpapri3652g73tvpm37ibn9','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1td6VO:YwyOP-2n1rXLIz3Qh9LniPsSa3o5ZzEpeUlSyBgBhDY','2025-02-12 11:45:14.265683'),('w45qvlq2t6u1r3ztj021nyhwef6nhtfl','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1t9RFL:S1DINM-2kWWQE7LZb-5AA3TyDg34JMpoxDWa9Fbu6IA','2024-11-22 15:50:03.679328'),('wovju9vsvxriodgq368ikuge4dmjmr16','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tARZ7:2oDDTyj_7bCrfuY07p9LwqbM5SbVXfYjBjZxkzA-1gg','2024-11-25 10:22:37.914023'),('ybr0dwjp4uumluwvu1ndcksyepw9y3mt','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tA3xU:CW8yfnb4dZHeUkYnSHPmkv8H8MJZSpU0InIFgprtfeU','2024-11-24 09:10:12.754439'),('zn5udav7pukdi41iz3w19gjpbwfyzmyd','.eJxVjDsOwjAQBe_iGll2Fv8o6XMGa71r4wBypDipEHeHSCmgfTPzXiLitta49bzEicVFaBCn3zEhPXLbCd-x3WZJc1uXKcldkQftcpw5P6-H-3dQsddvDWgxaJPOjgtyCk4VpQxpCoMLFiGDciZ5JLBQkgcOPmsLg3GZmEIR7w8J6zhA:1tAS9D:Pw1Hw0yqmjIBbL7Vhfi2J_IXUXkqM1cTsOVW-qP3aFE','2024-11-25 10:59:55.793282');
/*!40000 ALTER TABLE `django_session` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-04-30 14:42:43
