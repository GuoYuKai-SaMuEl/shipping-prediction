"""
Spark Batch Layer：歷史時序數據清洗與特徵工程
執行方式：python -m src.processing.spark_batch
"""
import os
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def create_session() -> SparkSession:
    return (
        SparkSession.builder
        .appName("ShippingRateBatchProcessor")
        .master("local[2]")
        .config("spark.driver.memory", "1g")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )


def load_timeseries(spark: SparkSession, path: str):
    return spark.read.option("header", True).option("inferSchema", True).csv(path)


def build_features(df):
    w7  = Window.orderBy("date").rowsBetween(-6, 0)
    w30 = Window.orderBy("date").rowsBetween(-29, 0)

    return (
        df.withColumn("oil_ma7",  F.avg("oil_price").over(w7))
          .withColumn("oil_ma30", F.avg("oil_price").over(w30))
          .withColumn("bdi_lag1", F.lag("bdi_index", 1).over(Window.orderBy("date")))
          .withColumn("bdi_pct_change",
                      (F.col("bdi_index") - F.col("bdi_lag1")) / F.col("bdi_lag1"))
          .withColumn("oil_bdi_ratio", F.col("oil_price") / F.col("bdi_index"))
          .dropna()
    )


def run(input_path: str = "data/raw/metrics/", output_path: str = "data/processed/features/"):
    spark = create_session()
    print("[Spark] 批次特徵工程啟動")
    df = load_timeseries(spark, input_path)
    features = build_features(df)
    features.write.mode("overwrite").parquet(output_path)
    print(f"[Spark] 特徵已輸出至 {output_path}，共 {features.count()} 筆")
    spark.stop()


if __name__ == "__main__":
    run()
